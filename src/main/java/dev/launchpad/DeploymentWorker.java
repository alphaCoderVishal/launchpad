package dev.launchpad;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

@Component
public class DeploymentWorker {
    private static final Logger log = LoggerFactory.getLogger(DeploymentWorker.class);
    private final Store store;
    private final WorkloadRuntime runtime;
    private final TransactionTemplate tx;
    private final MeterRegistry metrics;
    private final boolean enabled;
    private final int attempts;
    private final long delay;
    private final long deadlineMillis;
    public DeploymentWorker(Store store, WorkloadRuntime runtime, TransactionTemplate tx, MeterRegistry metrics,
        @Value("${launchpad.worker-enabled}") boolean enabled, @Value("${launchpad.health-attempts}") int attempts,
        @Value("${launchpad.health-delay-ms}") long delay, @Value("${launchpad.health-deadline-ms}") long deadlineMillis) {
        this.store = store; this.runtime = runtime; this.tx = tx; this.metrics = metrics;
        this.enabled = enabled; this.attempts = attempts; this.delay = delay;
        this.deadlineMillis = deadlineMillis;
        metrics.gauge("launchpad.queue.depth", store, s -> s.queue().size());
    }
    @Scheduled(fixedDelay = 1000)
    public synchronized void tick() {
        if (!enabled) return;
        // One control-plane process owns the file DB and this worker. DEPLOYING jobs are replayed after restart.
        for (var d : store.queue()) {
            try { execute(d.id()); }
            catch (Exception ex) { log.error("deployment={} reconciliation failed; will retry", d.id(), ex); }
        }
        cleanupRetired();
    }
    public synchronized void execute(String id) {
        var d = tx.execute(t -> {
            var current = store.deployment(id);
            store.lockedService(current.serviceName());
            current = store.deployment(id);
            if (!Set.of("QUEUED", "DEPLOYING").contains(current.status())) return null;
            if (current.status().equals("QUEUED")) store.status(id, "DEPLOYING", "Starting isolated candidate container");
            else store.event(id, "worker", "RECONCILED", "Resuming durable deployment after interruption");
            return store.deployment(id);
        });
        if (d == null) return;
        Timer.Sample timer = Timer.start(metrics);
        try {
            int port = runtime.ensureStarted(d);
            int successes = 0;
            long deadline = System.nanoTime() + java.util.concurrent.TimeUnit.MILLISECONDS.toNanos(deadlineMillis);
            for (int i = 0; i < attempts && System.nanoTime() < deadline; i++) {
                successes = runtime.healthy(port) ? successes + 1 : 0;
                if (successes >= 3) break;
                Thread.sleep(delay);
            }
            if (successes < 3) throw new IllegalStateException("Candidate failed three consecutive health checks within the configured deadline");
            tx.executeWithoutResult(t -> {
                store.lockedService(d.serviceName());
                store.jdbc().update("UPDATE services SET active_release=?,active_container=?,active_port=? WHERE name=?",
                    d.release(), d.candidateContainer(), port, d.serviceName());
                store.status(id, "SUCCEEDED", "Health gate passed; active route promoted atomically");
            });
            metrics.counter("launchpad.deployments", "result", "succeeded").increment();
            log.info("deployment={} service={} result=SUCCEEDED release={}", id, d.serviceName(), d.release());
        } catch (Exception ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
                // Keep DEPLOYING durable; a new worker can inspect the same candidate.
                return;
            }
            String reason = ex.getMessage() == null ? "Runtime failure" : ex.getMessage();
            String bounded = reason.substring(0, Math.min(400, reason.length()));
            tx.executeWithoutResult(t -> {
                var active = store.lockedService(d.serviceName());
                String state = active.activeContainer() == null ? "FAILED" : "ROLLED_BACK";
                store.status(id, state, bounded + "; prior active route retained");
            });
            metrics.counter("launchpad.deployments", "result", "failed").increment();
            log.warn("deployment={} service={} result={} reason={}", id, d.serviceName(), store.deployment(id).status(), bounded);
        } finally {
            timer.stop(metrics.timer("launchpad.deployment.duration"));
        }
        cleanupRetired();
    }
    private void cleanupRetired() {
        // Retain DB history as a durable cleanup ledger; repeat removal safely after crashes.
        for (var s : store.services("", true)) {
            for (var d : store.deployments(s.name())) {
                if (Set.of("SUCCEEDED", "FAILED", "ROLLED_BACK").contains(d.status())
                    && !d.candidateContainer().equals(s.activeContainer())
                    && store.events(d.id()).stream().noneMatch(e -> e.type().equals("CLEANED"))) {
                    try {
                        runtime.remove(d.candidateContainer());
                        store.event(d.id(), "worker", "CLEANED", "Retired or failed candidate removed");
                    } catch (Exception ex) { log.warn("deployment={} cleanup pending: {}", d.id(), ex.getMessage()); }
                }
            }
        }
    }
}
