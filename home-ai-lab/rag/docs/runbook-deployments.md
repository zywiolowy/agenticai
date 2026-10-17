# Deployment runbook

## How deployments work
All services are deployed with GitOps. The desired state lives in the `platform-config` Git repository.
Argo CD watches the repository and syncs every change to the Kubernetes cluster within 3 minutes.
Nobody runs `kubectl apply` against production by hand.

## Rolling back a bad deployment
1. Find the commit that introduced the problem in `platform-config`.
2. Run `git revert <commit>` and push to main. This is the preferred rollback.
3. Argo CD syncs the reverted state automatically. Check the application status in the Argo CD UI.
4. In an emergency you may use "Rollback" in the Argo CD UI, but you must still create the Git revert
   afterwards, otherwise Argo CD will re-apply the bad version on the next sync.

## Change approval
Every production change needs a pull request with one approval from the platform team.
Changes to the regulated product pipeline also need approval from Quality Assurance and a change record.
