"""Direct API transport with useful errors for multi-address LAN hosts."""
import sys
sys.dont_write_bytecode = True
import http.client
import socket
import urllib.error
import urllib.request


def connect(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    # Try every resolved address, retaining failures instead of hiding an IPv4
    # refusal behind the final IPv6 'network unreachable' error.
    host, port = address
    failures = []
    for family, kind, protocol, _, endpoint in socket.getaddrinfo(
            host, port, 0, socket.SOCK_STREAM):
        connection = socket.socket(family, kind, protocol)
        try:
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                connection.settimeout(timeout)
            if source_address:
                connection.bind(source_address)
            connection.connect(endpoint)
            return connection
        except OSError as error:
            connection.close()
            resolved_host = f'[{endpoint[0]}]' if family == socket.AF_INET6 else endpoint[0]
            failures.append(f'{resolved_host}:{port}: {error}')
    raise OSError('Cannot connect to API host ' + host + ': ' +
                  ('; '.join(failures) or 'no usable addresses'))


class DirectConnection(http.client.HTTPConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = connect


class DirectHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = connect


class HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, request):
        return self.do_open(DirectConnection, request)


class HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(DirectHTTPSConnection, request,
                            context=self._context)


# These clients target a directly accessible llama-server, including LAN hosts.
# Ignore inherited HTTP(S)_PROXY settings; keep normal TLS verification enabled.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                     HTTPHandler(), HTTPSHandler())


def urlopen(request, timeout):
    try:
        return _opener.open(request, timeout=timeout)
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as error:
        raise urllib.error.URLError(
            f'{error.reason}. Check server listening address, published port, '
            'firewall and network route; remote access requires a server port '
            'bound to a LAN address rather than localhost.') from None
