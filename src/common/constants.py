# Shared project constants

# Default piece size used when splitting a file into chunks for download/upload.
DEFAULT_PIECE_SIZE = 256 * 1024

# Default tracker location used when a peer is started without custom settings.
DEFAULT_TRACKER_HOST = "127.0.0.1"
DEFAULT_TRACKER_PORT = 6969

# Default port used by peers when they listen for incoming connections.
DEFAULT_PEER_PORT = 6881

# How often a peer announces its status to the tracker.
ANNOUNCE_INTERVAL = 30

# Time-to-live for peer state before it is considered stale.
PEER_TTL = 90

# Maximum number of peers returned by the tracker in one response.
MAX_PEERS_RETURNED = 3

# Maximum number of bytes a peer requests in a single block read.
MAX_TRACKER_REQUEST_BYTES = 64 * 1024
MAX_REQUEST_BYTES = MAX_TRACKER_REQUEST_BYTES

# Maximum complete protocol message size accepted over a peer connection.
# This protects the peer from trying to receive an unexpectedly huge message.
MAX_MESSAGE_SIZE = 16 * 1024 * 1024

# Socket inactivity timeout before a connection is treated as dead.
SOCKET_TIMEOUT = 10

# Text encoding used for network payloads and metadata strings.
ENCODING = "utf-8"

# Request pipelining and timeout configuration.
MAX_PIPELINE_REQUESTS = 4
REQUEST_TIMEOUT = 15.0

# Tit-for-tat choking policy.
CHOKING_INTERVAL = 10.0
MAX_UNCHOKED_PEERS = 4