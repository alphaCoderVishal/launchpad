package dev.launchpad;

import java.net.URI;
import java.net.HttpURLConnection;
import java.net.Proxy;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class DockerRuntime implements WorkloadRuntime {
    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(DockerRuntime.class);
    private final String image;
    private final String namespace;
    private final long timeoutSeconds;
    public DockerRuntime(@Value("${launchpad.docker-image}") String image, @Value("${launchpad.namespace}") String namespace,
        @Value("${launchpad.docker-timeout-seconds}") long timeoutSeconds) {
        this.image = image; this.namespace = namespace; this.timeoutSeconds = timeoutSeconds;
    }
    @Override public int ensureStarted(Store.Deployment d) {
        // Deterministic names make replay after a process crash safe. Never run user-provided commands/images.
        var inspect = command(false, "inspect", "--format", "{{json .Config.Labels}}", d.candidateContainer());
        if (inspect.code() == 0) {
            if (!owned(inspect.output())) throw new IllegalStateException("Container ownership mismatch");
            command(true, "start", d.candidateContainer());
        } else {
            command(true, "run", "-d", "--pull=never", "--name", d.candidateContainer(),
                "--label", "dev.launchpad.namespace=" + namespace,
                "--label", "dev.launchpad.deployment=" + d.id(),
                "--memory=64m", "--cpus=0.25", "--pids-limit=64", "--read-only",
                "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=10001:10001",
                "-p", "127.0.0.1::8000", "-e", "APP_VERSION=" + d.release(), image);
        }
        String mapping = command(true, "port", d.candidateContainer(), "8000/tcp").output().strip();
        if (!mapping.matches("127\\.0\\.0\\.1:[0-9]+")) throw new IllegalStateException("Unexpected workload port mapping");
        return Integer.parseInt(mapping.substring(mapping.lastIndexOf(':') + 1));
    }
    @Override public boolean healthy(int port) {
        try {
            int status = request(port, "/health").status();
            if (status != 200) log.debug("workloadPort={} healthStatus={}", port, status);
            return status == 200;
        }
        catch (Exception ex) { log.debug("workloadPort={} probeFailure={}", port, ex.toString()); return false; }
    }
    @Override public String response(int port) {
        try {
            var res = request(port, "/");
            if (res.status() != 200) throw new IllegalStateException("Workload returned non-success");
            return res.body();
        } catch (Exception ex) { throw new ApiException(org.springframework.http.HttpStatus.BAD_GATEWAY, "Active workload unavailable"); }
    }
    private record HttpResult(int status, String body) {}
    private HttpResult request(int port, String path) throws Exception {
        var connection = (HttpURLConnection) URI.create("http://127.0.0.1:" + port + path).toURL().openConnection(Proxy.NO_PROXY);
        connection.setConnectTimeout(2000); connection.setReadTimeout(2000);
        connection.setInstanceFollowRedirects(false);
        try {
            int status = connection.getResponseCode();
            var stream = status < 400 ? connection.getInputStream() : connection.getErrorStream();
            if (stream == null) return new HttpResult(status, "");
            try (stream) { return new HttpResult(status, new String(stream.readNBytes(8192), java.nio.charset.StandardCharsets.UTF_8)); }
        } finally { connection.disconnect(); }
    }
    @Override public void remove(String container) {
        if (container == null) return;
        var inspect = command(false, "inspect", "--format", "{{json .Config.Labels}}", container);
        if (inspect.code() != 0) {
            // A missing container is already removed; daemon errors must not look like successful cleanup.
            if (inspect.output().contains("No such object")) return;
            throw new IllegalStateException("Docker inspect failed during cleanup");
        }
        if (!owned(inspect.output())) throw new IllegalStateException("Refusing to remove unowned container");
        command(true, "rm", "-f", container);
    }
    private boolean owned(String labels) {
        try { return namespace.equals(new com.fasterxml.jackson.databind.ObjectMapper().readTree(labels).path("dev.launchpad.namespace").asText()); }
        catch (Exception ex) { throw new IllegalStateException("Invalid container labels", ex); }
    }
    private record Result(int code, String output) {}
    private Result command(boolean requireSuccess, String... args) {
        List<String> argv = new ArrayList<>(); argv.add("docker"); argv.addAll(List.of(args));
        // Redirect to a temporary file so a noisy subprocess cannot deadlock on its output pipe.
        java.nio.file.Path output = null;
        try {
            output = java.nio.file.Files.createTempFile("launchpad-docker-", ".log");
            var process = new ProcessBuilder(argv).redirectErrorStream(true).redirectOutput(output.toFile()).start();
            if (!process.waitFor(timeoutSeconds, TimeUnit.SECONDS)) {
                process.destroyForcibly(); throw new IllegalStateException("Docker command timed out");
            }
            String text = java.nio.file.Files.readString(output);
            if (requireSuccess && process.exitValue() != 0) throw new IllegalStateException("Docker command failed: " + text.substring(0, Math.min(250, text.length())).strip());
            return new Result(process.exitValue(), text);
        } catch (InterruptedException ex) { Thread.currentThread().interrupt(); throw new IllegalStateException("Docker command interrupted", ex); }
        catch (java.io.IOException ex) { throw new IllegalStateException("Docker CLI unavailable", ex); }
        finally { if (output != null) try { java.nio.file.Files.deleteIfExists(output); } catch (java.io.IOException ignored) {} }
    }
}
