from dify_plugin import Plugin, DifyPluginEnv
import logging

plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=120))

# global logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # output to the console
    ]
)

# set the logging level for specific modules
# set the logging level of the Dify plugin system to WARNING, so only warnings and errors will be displayed, not INFO
logging.getLogger('dify_plugin').setLevel(logging.WARNING)
# if you only want to block specific modules, you can set it more precisely
logging.getLogger('dify_plugin.core.server.tcp.request_reader').setLevel(logging.WARNING)

if __name__ == '__main__':
    plugin.run()
