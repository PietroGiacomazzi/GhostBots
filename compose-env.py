import os, argparse, subprocess
import docker_tools.tools as tl

parser = argparse.ArgumentParser()
parser.add_argument("env", help='Environment folder to use')
args = parser.parse_args()

envname = args.env

tl.configure_env('greedyghost', envname)

tl.compose_env()
   


