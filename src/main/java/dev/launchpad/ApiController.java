package dev.launchpad;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class ApiController {
    private final Store store;
    private final ControlPlane plane;
    private final WorkloadRuntime runtime;
    public ApiController(Store store, ControlPlane plane, WorkloadRuntime runtime) { this.store = store; this.plane = plane; this.runtime = runtime; }
    public record Register(@NotBlank @Pattern(regexp = "[a-z][a-z0-9-]{2,39}") String name) {}
    public record Deploy(@NotBlank @Pattern(regexp = "v1|v2|bad-health") String release,
                         @NotBlank @Pattern(regexp = "dev|prod") String environment) {}
    private boolean ops(Authentication a) { return a.getAuthorities().stream().anyMatch(r -> r.getAuthority().equals("ROLE_OPERATOR")); }
    @GetMapping("/me") Map<String, Object> me(Authentication a) { return Map.of("name", a.getName(), "operator", ops(a)); }
    @GetMapping("/services") List<Store.Service> services(Authentication a) { return store.services(a.getName(), ops(a)); }
    @PostMapping(value = "/services", consumes = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    Store.Service register(@Valid @RequestBody Register body, Authentication a) { return plane.register(body.name(), a.getName()); }
    @GetMapping("/services/{name}") Store.Service service(@PathVariable String name, Authentication a) { return plane.authorize(name, a.getName(), ops(a)); }
    @PostMapping(value = "/services/{name}/deployments", consumes = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.ACCEPTED)
    Store.Deployment deploy(@PathVariable String name, @Valid @RequestBody Deploy body,
        @RequestHeader("Idempotency-Key") String key, Authentication a) {
        if (!key.matches("[A-Za-z0-9_-]{8,80}")) throw new ApiException(HttpStatus.BAD_REQUEST, "Idempotency-Key must be 8-80 letters, digits, underscores or hyphens");
        return plane.submit(name, body.release(), body.environment(), key, a.getName(), ops(a));
    }
    @GetMapping("/services/{name}/deployments") List<Store.Deployment> deployments(@PathVariable String name, Authentication a) {
        plane.authorize(name, a.getName(), ops(a)); return store.deployments(name);
    }
    @GetMapping("/deployments/{id}") Store.Deployment deployment(@PathVariable String id, Authentication a) {
        var d = store.deployment(id); plane.authorize(d.serviceName(), a.getName(), ops(a)); return d;
    }
    @PostMapping("/deployments/{id}/approve") Store.Deployment approve(@PathVariable String id, Authentication a) { return plane.approve(id, a.getName()); }
    @PostMapping("/deployments/{id}/cancel") Store.Deployment cancel(@PathVariable String id, Authentication a) { return plane.cancel(id, a.getName(), ops(a)); }
    @GetMapping("/deployments/{id}/events") List<Store.Event> events(@PathVariable String id, Authentication a) {
        var d = store.deployment(id); plane.authorize(d.serviceName(), a.getName(), ops(a)); return store.events(id);
    }
    @GetMapping(value = "/services/{name}/response", produces = MediaType.APPLICATION_JSON_VALUE)
    String response(@PathVariable String name, Authentication a) {
        var s = plane.authorize(name, a.getName(), ops(a));
        if (s.activePort() == null) throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "No healthy deployment is active");
        return runtime.response(s.activePort());
    }
}
