import sys

# Strip ROS/ament paths that may be injected via PYTHONPATH.
# They register pytest plugins incompatible with this project's pytest version.
# The preferred fix is to run tests with PYTHONPATH="" (see docs/tests/local.md).
# This filter is a safety net when PYTHONPATH is not cleared first.
sys.path = [p for p in sys.path if "/opt/ros" not in p and "/ament" not in p]
