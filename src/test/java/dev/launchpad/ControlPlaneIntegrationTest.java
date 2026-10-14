package dev.launchpad;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = {"spring.datasource.url=jdbc:h2:mem:tests;DB_CLOSE_DELAY=-1", "launchpad.worker-enabled=false",
    "launchpad.health-delay-ms=1", "launchpad.health-attempts=3"})
@AutoConfigureMockMvc
@org.springframework.boot.test.autoconfigure.actuate.observability.AutoConfigureObservability
class ControlPlaneIntegrationTest {
    static final String DEV = "Bearer local-developer-token-change-me";
    static final String OTHER = "Bearer local-other-token-change-me";
    static final String OPS = "Bearer local-operator-token-change-me";
    @Autowired MockMvc mvc;
    @Autowired Store store;
    @Autowired ControlPlane plane;
    @Autowired DeploymentWorker worker;
    @Autowired FakeRuntime runtime;
    @BeforeEach void reset() {
        store.jdbc().update("DELETE FROM audit_events"); store.jdbc().update("DELETE FROM deployments"); store.jdbc().update("DELETE FROM services");
        runtime.reset();
        plane.register("checkout", "vishal");
    }
    @Test void unauthenticatedAndMalformedTokensAreRejected() throws Exception {
        mvc.perform(get("/api/services")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/services").header("Authorization", "Bearer bad")).andExpect(status().isUnauthorized());
        mvc.perform(get("/actuator/health")).andExpect(status().isOk());
    }
    @Test void teamIsolationCoversReadsWritesAndTimelines() throws Exception {
        var d = submit("v1", "dev", "isolation-key");
        mvc.perform(get("/api/services/checkout").header("Authorization", OTHER)).andExpect(status().isNotFound());
        mvc.perform(get("/api/deployments/" + d.id() + "/events").header("Authorization", OTHER)).andExpect(status().isNotFound());
        mvc.perform(post("/api/services/checkout/deployments").header("Authorization", OTHER).header("Idempotency-Key", "another-key")
            .contentType(MediaType.APPLICATION_JSON).content("{\"release\":\"v1\",\"environment\":\"dev\"}")).andExpect(status().isNotFound());
        mvc.perform(get("/api/services").header("Authorization", OTHER)).andExpect(content().json("[]"));
    }
    @Test void invalidAndUnknownInputsCannotBecomeDockerArguments() throws Exception {
        mvc.perform(post("/api/services").header("Authorization", DEV).contentType(MediaType.APPLICATION_JSON)
            .content("{\"name\":\"x;rm -rf /\"}")).andExpect(status().isBadRequest());
        mvc.perform(post("/api/services/checkout/deployments").header("Authorization", DEV).header("Idempotency-Key", "safe-key-1")
            .contentType(MediaType.APPLICATION_JSON).content("{\"release\":\"arbitrary/image\",\"environment\":\"dev\"}")).andExpect(status().isBadRequest());
        mvc.perform(post("/api/services").header("Authorization", DEV).contentType(MediaType.APPLICATION_JSON)
            .content("{\"name\":\"billing\",\"owner\":\"other-team\"}")).andExpect(status().isBadRequest());
    }
    @Test void idempotencyReplayAndPayloadConflict() {
        var d = submit("v1", "dev", "replay-key-1");
        assertThat(submit("v1", "dev", "replay-key-1").id()).isEqualTo(d.id());
        assertThat(store.deployments("checkout")).hasSize(1);
        assertThatThrownBy(() -> submit("v2", "dev", "replay-key-1")).isInstanceOf(ApiException.class).hasMessageContaining("different request");
        worker.execute(d.id());
        assertThat(submit("v1", "dev", "replay-key-1").status()).isEqualTo("SUCCEEDED");
    }
    @Test void concurrentRequestsHaveOneDeployment() throws Exception {
        try (var pool = Executors.newFixedThreadPool(4)) {
            var tasks = java.util.stream.IntStream.range(0, 8).<java.util.concurrent.Callable<String>>mapToObj(i ->
                () -> submit("v1", "dev", "concurrent-key").id()).toList();
            var results = pool.invokeAll(tasks);
            var ids = new java.util.HashSet<String>();
            for (var result : results) ids.add(result.get());
            assertThat(ids).hasSize(1);
            assertThat(store.deployments("checkout")).hasSize(1);
        }
    }
    @Test void inFlightDeploymentPreventsRacingPromotions() {
        submit("v1", "dev", "first-request");
        assertThatThrownBy(() -> submit("v2", "dev", "second-request")).hasMessageContaining("in-flight");
    }
    @Test void productionNeedsOperatorApproval() throws Exception {
        var d = submit("v1", "prod", "production-key");
        worker.execute(d.id());
        assertThat(runtime.started).isEmpty();
        mvc.perform(post("/api/deployments/" + d.id() + "/approve").header("Authorization", DEV)).andExpect(status().isForbidden());
        mvc.perform(post("/api/deployments/" + d.id() + "/approve").header("Authorization", OPS)).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("QUEUED"));
        worker.execute(d.id());
        assertThat(store.deployment(d.id()).status()).isEqualTo("SUCCEEDED");
        assertThat(store.events(d.id())).anyMatch(e -> e.type().equals("APPROVED") && e.actor().equals("platform-ops"));
    }
    @Test void happyPathPromotesAndCleansPreviousContainer() {
        var first = submit("v1", "dev", "healthy-first"); worker.execute(first.id());
        var next = submit("v2", "dev", "healthy-next"); worker.execute(next.id());
        assertThat(store.service("checkout").activeRelease()).isEqualTo("v2");
        assertThat(runtime.removed).contains(first.candidateContainer()).doesNotContain(next.candidateContainer());
        assertThat(store.events(next.id())).extracting(Store.Event::type).containsExactly("REQUESTED", "DEPLOYING", "SUCCEEDED");
    }
    @Test void failedHealthGateRetainsPriorRoute() {
        var first = submit("v1", "dev", "rollback-first"); worker.execute(first.id());
        var failed = submit("bad-health", "dev", "rollback-bad"); worker.execute(failed.id());
        assertThat(store.deployment(failed.id()).status()).isEqualTo("ROLLED_BACK");
        assertThat(store.service("checkout").activeContainer()).isEqualTo(first.candidateContainer());
        assertThat(runtime.removed).contains(failed.candidateContainer()).doesNotContain(first.candidateContainer());
    }
    @Test void firstDeploymentFailureDoesNotInventAnActiveRelease() {
        var d = submit("bad-health", "dev", "first-bad-key"); worker.execute(d.id());
        assertThat(store.deployment(d.id()).status()).isEqualTo("FAILED");
        assertThat(store.service("checkout").activePort()).isNull();
    }
    @Test void interruptedDeploymentReconcilesDeterministically() {
        var d = submit("v1", "dev", "recovery-key");
        store.jdbc().update("UPDATE deployments SET status='DEPLOYING' WHERE id=?", d.id());
        runtime.ensureStarted(d); // Represents candidate created just before control-plane interruption.
        worker.execute(d.id());
        assertThat(runtime.started).hasSize(1);
        assertThat(store.deployment(d.id()).status()).isEqualTo("SUCCEEDED");
        assertThat(store.events(d.id())).anyMatch(e -> e.type().equals("RECONCILED"));
    }
    @Test void dockerFailureBecomesAuditableFailure() {
        runtime.failStart = true;
        var d = submit("v1", "dev", "docker-failure"); worker.execute(d.id());
        assertThat(store.deployment(d.id()).status()).isEqualTo("FAILED");
        assertThat(store.events(d.id())).anyMatch(e -> e.type().equals("FAILED") && e.detail().contains("daemon unavailable"));
    }
    @Test void cancellationReleasesServiceAndIsOwnerScoped() throws Exception {
        var d = submit("v1", "prod", "cancel-me-key");
        mvc.perform(post("/api/deployments/" + d.id() + "/cancel").header("Authorization", OTHER)).andExpect(status().isNotFound());
        mvc.perform(post("/api/deployments/" + d.id() + "/cancel").header("Authorization", DEV)).andExpect(status().isOk());
        worker.execute(d.id()); assertThat(runtime.started).isEmpty();
        assertThat(submit("v2", "dev", "after-cancel").status()).isEqualTo("QUEUED");
    }
    @Test void quotaIsEnforcedAndDuplicateNamesAreConflicts() {
        assertThatThrownBy(() -> plane.register("checkout", "vishal")).isInstanceOf(ApiException.class);
        for (int i = 0; i < 4; i++) plane.register("service-" + i, "vishal");
        assertThatThrownBy(() -> plane.register("over-quota", "vishal")).hasMessageContaining("quota");
    }
    @Test void metricsAreOperatorOnly() throws Exception {
        mvc.perform(get("/actuator/prometheus").header("Authorization", DEV)).andExpect(status().isForbidden());
        mvc.perform(get("/actuator/prometheus").header("Authorization", OPS)).andExpect(status().isOk());
    }
    @Test void intermittentHealthDoesNotPassTheConsecutiveGate() {
        runtime.probes.addAll(java.util.List.of(true, false, true));
        var d = submit("v1", "dev", "flapping-key"); worker.execute(d.id());
        assertThat(store.deployment(d.id()).status()).isEqualTo("FAILED");
        assertThat(store.service("checkout").activePort()).isNull();
    }
    @Test void failedCleanupRemainsRetryableWithoutChangingTheActiveRoute() {
        var first = submit("v1", "dev", "cleanup-first"); worker.execute(first.id());
        runtime.failRemoveOnce = true;
        var next = submit("v2", "dev", "cleanup-next"); worker.execute(next.id());
        assertThat(store.service("checkout").activeRelease()).isEqualTo("v2");
        assertThat(store.events(first.id())).noneMatch(e -> e.type().equals("CLEANED"));
        var third = submit("v1", "dev", "cleanup-retry"); worker.execute(third.id());
        assertThat(store.events(first.id())).anyMatch(e -> e.type().equals("CLEANED"));
        assertThat(store.deployment(next.id()).status()).isEqualTo("SUCCEEDED");
    }
    private Store.Deployment submit(String release, String env, String key) { return plane.submit("checkout", release, env, key, "vishal", false); }
    @TestConfiguration static class RuntimeConfig {
        @Bean @Primary FakeRuntime fakeRuntime() { return new FakeRuntime(); }
    }
    static class FakeRuntime implements WorkloadRuntime {
        final Map<String, Integer> started = new ConcurrentHashMap<>();
        final Map<Integer, Boolean> health = new ConcurrentHashMap<>();
        final java.util.Set<String> removed = ConcurrentHashMap.newKeySet();
        boolean failStart;
        boolean failRemoveOnce;
        final java.util.Queue<Boolean> probes = new java.util.concurrent.ConcurrentLinkedQueue<>();
        void reset() { started.clear(); health.clear(); removed.clear(); probes.clear(); failStart = false; failRemoveOnce = false; }
        public int ensureStarted(Store.Deployment d) {
            if (failStart) throw new IllegalStateException("daemon unavailable");
            int port = started.computeIfAbsent(d.candidateContainer(), k -> 12000 + started.size());
            health.put(port, !d.release().equals("bad-health")); return port;
        }
        public boolean healthy(int port) { return probes.isEmpty() ? health.getOrDefault(port, false) : probes.remove(); }
        public void remove(String container) {
            if (failRemoveOnce) { failRemoveOnce = false; throw new IllegalStateException("daemon temporarily unavailable"); }
            removed.add(container);
        }
        public String response(int port) { return "{\"healthy\":true}"; }
    }
}
