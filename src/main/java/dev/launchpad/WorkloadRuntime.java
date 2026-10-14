package dev.launchpad;

public interface WorkloadRuntime {
    int ensureStarted(Store.Deployment deployment);
    boolean healthy(int port);
    void remove(String container);
    String response(int port);
}
