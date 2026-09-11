import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import uvicorn
from cognishift.app.config import settings

def main():
    """Run the CogniShift sovereign backend server."""
    uvicorn.run(
        "cognishift.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False
    )

if __name__ == "__main__":
    main()
