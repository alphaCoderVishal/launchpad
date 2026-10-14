package dev.launchpad;

import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

@Repository
public class Store {
    private final JdbcTemplate db;
    public Store(JdbcTemplate db) { this.db = db; }
    JdbcTemplate jdbc() { return db; }
    public record Service(String name, String owner, String activeRelease, String activeContainer, Integer activePort, String createdAt) {}
    public record Deployment(String id, String serviceName, String release, String environment, String requestedBy,
        String requestKey, String status, String detail, String candidateContainer, String createdAt, String updatedAt) {}
    public record Event(long id, String deploymentId, String actor, String type, String detail, String createdAt) {}
    private static final RowMapper<Service> SERVICE = (r, i) -> new Service(r.getString("name"), r.getString("owner"),
        r.getString("active_release"), r.getString("active_container"), (Integer) r.getObject("active_port"), r.getObject("created_at", java.time.OffsetDateTime.class).toString());
    private static final RowMapper<Deployment> DEPLOYMENT = (r, i) -> new Deployment(r.getString("id"), r.getString("service_name"),
        r.getString("release_name"), r.getString("environment"), r.getString("requested_by"), r.getString("request_key"),
        r.getString("status"), r.getString("detail"), r.getString("candidate_container"), r.getObject("created_at", java.time.OffsetDateTime.class).toString(), r.getObject("updated_at", java.time.OffsetDateTime.class).toString());
    List<Service> services(String user, boolean ops) { return ops ? db.query("SELECT * FROM services ORDER BY name", SERVICE)
        : db.query("SELECT * FROM services WHERE owner=? ORDER BY name", SERVICE, user); }
    Service service(String name) { return db.query("SELECT * FROM services WHERE name=?", SERVICE, name).stream().findFirst().orElseThrow(ApiException::missing); }
    Service lockedService(String name) { return db.query("SELECT * FROM services WHERE name=? FOR UPDATE", SERVICE, name).stream().findFirst().orElseThrow(ApiException::missing); }
    Deployment deployment(String id) { return db.query("SELECT * FROM deployments WHERE id=?", DEPLOYMENT, id).stream().findFirst().orElseThrow(ApiException::missing); }
    Deployment byKey(String actor, String key) { return db.query("SELECT * FROM deployments WHERE requested_by=? AND request_key=?", DEPLOYMENT, actor, key).stream().findFirst().orElse(null); }
    List<Deployment> deployments(String service) { return db.query("SELECT * FROM deployments WHERE service_name=? ORDER BY created_at DESC", DEPLOYMENT, service); }
    List<Deployment> queue() { return db.query("SELECT * FROM deployments WHERE status IN ('QUEUED','DEPLOYING') ORDER BY created_at", DEPLOYMENT); }
    List<Event> events(String id) { return db.query("SELECT * FROM audit_events WHERE deployment_id=? ORDER BY id", (r, i) ->
        new Event(r.getLong("id"), r.getString("deployment_id"), r.getString("actor"), r.getString("event_type"), r.getString("detail"), r.getObject("created_at", java.time.OffsetDateTime.class).toString()), id); }
    void event(String id, String actor, String type, String detail) {
        db.update("INSERT INTO audit_events(deployment_id,actor,event_type,detail) VALUES (?,?,?,?)", id, actor, type, detail);
    }
    void status(String id, String status, String detail) {
        db.update("UPDATE deployments SET status=?,detail=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", status, detail, id);
        event(id, "worker", status, detail);
    }
}
