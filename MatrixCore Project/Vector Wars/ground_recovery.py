from enum import Enum


class GroundRecoveryStatus(Enum):
    DEPLOYED = "DEPLOYED"
    REDEPLOY_REQUIRED = "REDEPLOY_REQUIRED"


class GroundRecoveryAuthority:
    """Ground-only failure/redeploy state independent of rendering.

    A destroyed player unit does not immediately respawn. The operation remains
    intact until the player deliberately requests redeployment.
    """

    def __init__(self):
        self.status = GroundRecoveryStatus.DEPLOYED
        self.failures = 0
        self.redeployments = 0

    @property
    def redeploy_required(self) -> bool:
        return self.status is GroundRecoveryStatus.REDEPLOY_REQUIRED

    def record_loss(self) -> bool:
        """Enter the loss state once. Returns True only on the transition."""
        if self.redeploy_required:
            return False
        self.failures += 1
        self.status = GroundRecoveryStatus.REDEPLOY_REQUIRED
        return True

    def request_redeploy(self) -> bool:
        """Consume a pending loss and return to active deployment."""
        if not self.redeploy_required:
            return False
        self.redeployments += 1
        self.status = GroundRecoveryStatus.DEPLOYED
        return True

    def diagnostic_text(self) -> str:
        return (
            f"GROUND RECOVERY // {self.status.value} // LOSSES {self.failures} // "
            f"REDEPLOYS {self.redeployments}"
        )
