import json
import sys

from cmd_router.src.lib import *

if __name__ == "__main__":
    print(CommandRouter.hello())
    print(json.dumps(CommandRouter.data().get("info")), file=sys.stderr)
