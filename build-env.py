# todo 2 builds, one with the build number tag

import os,  argparse, subprocess, time, json
import docker_tools.tools as tl
#parser = argparse.ArgumentParser()
#parser.add_argument("env", help='Environment folder to use')
#args = parser.parse_args()

#envname = args.env
envname =  'build'
envdir = tl.validate_environment_config(envname)

tl.configure_env('greedyghost', envname)

tl.cleanup_for_build()

tl.build()

tl.compose_env()

tl.compose_down_env()

print("done.")