package dev.launchpad;

import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class ControlPlane {
    private final Store store;
    private final TransactionTemplate tx;
    private final String namespace;
    public ControlPlane(Store store, TransactionTemplate tx, @Value("${launchpad.namespace}") String namespace) {
        this.store = store; this.tx = tx; this.namespace = namespace;
        if (!namespace.matches("[a-z][a-z0-9-]{0,24}")) throw new IllegalArgumentException("Invalid namespace");
    }
    Store.Service authorize(String name, String actor, boolean ops) {
        var s = store.service(name);
        // Hide cross-team names instead of exposing ownership through a 403.
        if (!ops && !s.owner().equals(actor)) throw ApiException.missing();
        return s;
    }
    Store.Service register(String name, String actor) {
        try {
            return tx.execute(t -> {
                // One lock serializes quota checks without a separate cache.
                store.jdbc().queryForObject("SELECT id FROM quota_lock WHERE id=1 FOR UPDATE", Integer.class);
                if (store.services(actor, false).size() >= 5) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "Team quota is five services");
                store.jdbc().update("INSERT INTO services(name,owner) VALUES (?,?)", name, actor);
                return store.service(name);
            });
        } catch (DuplicateKeyException ex) { throw ApiException.conflict("Service name already registered"); }
    }
    Store.Deployment submit(String name, String release, String environment, String key, String actor, boolean ops) {
        authorize(name, actor, ops);
        try {
            return tx.execute(t -> {
                store.lockedService(name); // Serialize same-service submissions and promotions.
                var previous = store.byKey(actor, key);
                if (previous != null) return replay(previous, name, release, environment);
                boolean busy = store.deployments(name).stream().anyMatch(d ->
                    java.util.Set.of("WAITING_APPROVAL", "QUEUED", "DEPLOYING").contains(d.status()));
                if (busy) throw ApiException.conflict("Service already has an in-flight deployment");
                String id = UUID.randomUUID().toString();
                String state = environment.equals("prod") ? "WAITING_APPROVAL" : "QUEUED";
                String detail = environment.equals("prod") ? "Operator approval required" : "Accepted for health-gated deployment";
                store.jdbc().update("INSERT INTO deployments(id,service_name,release_name,environment,requested_by,request_key,status,detail,candidate_container) VALUES (?,?,?,?,?,?,?,?,?)",
                    id, name, release, environment, actor, key, state, detail, namespace + "-" + id);
                store.event(id, actor, "REQUESTED", detail);
                return store.deployment(id);
            });
        } catch (DuplicateKeyException ex) {
            var previous = store.byKey(actor, key);
            if (previous == null) throw ApiException.conflict("Concurrent request; retry with the same key");
            return replay(previous, name, release, environment);
        }
    }
    private Store.Deployment replay(Store.Deployment d, String name, String release, String env) {
        if (!d.serviceName().equals(name) || !d.release().equals(release) || !d.environment().equals(env))
            throw ApiException.conflict("Idempotency key was already used for a different request");
        return d;
    }
    Store.Deployment approve(String id, String actor) {
        return tx.execute(t -> {
            var d = store.deployment(id);
            store.lockedService(d.serviceName());
            d = store.deployment(id);
            if (d.status().equals("QUEUED")) return d;
            if (!d.status().equals("WAITING_APPROVAL")) throw ApiException.conflict("Deployment is not waiting for approval");
            store.jdbc().update("UPDATE deployments SET status='QUEUED',detail='Approved',updated_at=CURRENT_TIMESTAMP WHERE id=?", id);
            store.event(id, actor, "APPROVED", "Operator approved production promotion");
            return store.deployment(id);
        });
    }
    Store.Deployment cancel(String id, String actor, boolean ops) {
        var original = store.deployment(id);
        authorize(original.serviceName(), actor, ops);
        return tx.execute(t -> {
            store.lockedService(original.serviceName());
            var d = store.deployment(id);
            if (d.status().equals("CANCELLED")) return d;
            if (!java.util.Set.of("WAITING_APPROVAL", "QUEUED").contains(d.status()))
                throw ApiException.conflict("Only pending deployments can be cancelled");
            store.jdbc().update("UPDATE deployments SET status='CANCELLED',detail='Cancelled before execution',updated_at=CURRENT_TIMESTAMP WHERE id=?", id);
            store.event(id, actor, "CANCELLED", "Cancelled before execution");
            return store.deployment(id);
        });
    }
}
