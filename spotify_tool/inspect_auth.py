import spotapi
import inspect
from spotapi.http.request import TLSClient

try:
    print(inspect.getsource(TLSClient.authenticate))
except Exception as e:
    print(f"Error: {e}")
