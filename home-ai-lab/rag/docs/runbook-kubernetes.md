# Kubernetes troubleshooting runbook

## Pod in CrashLoopBackOff
1. Run `kubectl describe pod <pod>` and read the Events section (image pull errors, OOMKilled, probes).
2. Check the logs of the crashed container with `kubectl logs <pod> --previous`.
3. If the reason is OOMKilled, raise the memory limit or fix the leak; check the Grafana memory panel.
4. If a liveness probe fails, check that the probe path and port are correct and the start-up time is long enough.

## Pod stuck in Pending
Usually there are not enough resources or no node matches the selector or toleration.
Run `kubectl describe pod` and look for "FailedScheduling". GPU pods need the `nvidia.com/gpu` resource.

## Scaling
Stateless services use a HorizontalPodAutoscaler on CPU at 70%. Do not scale StatefulSets such as Qdrant
with an HPA; add replicas and shards deliberately.
