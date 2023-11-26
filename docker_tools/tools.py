import os, semantic_version, subprocess, json

#pip install yaml-env-var-parser
import yaml_env_var_parser as yaml_env

ENVVAR_PROJECT_TARGET_SOFTWAREVERSION = 'PROJECT_TARGET_SOFTWAREVERSION'
ENVVAR_PROJECT_PROJNAME = 'PROJECT_PROJNAME'
ENVVAR_PROJECT_ENVNAME = 'PROJECT_ENVNAME'

# Configuration is handledd with nev variables. one day i might create a configuration class if we want to maanage multiple projects at onco
# from this library's perspective, the only thing an environment folder needs is a overrides file called 'docker-compose.overrides.yml', everything else is project specific

class ToolScriptError(Exception):
    pass

def configure_env(project_name: str = '', environment: str = '', software_version: str = '', **additional: str) -> None:
    """ Set up environmental variables connected to the project """
    validate_environment_config(environment)
    os.environ[ENVVAR_PROJECT_ENVNAME] = environment
    os.environ[ENVVAR_PROJECT_PROJNAME] = project_name
    os.environ[ENVVAR_PROJECT_TARGET_SOFTWAREVERSION] = software_version if software_version != '' else str(get_current_version())

    for k, v in additional.items():
        os.environ[k] = v

def get_docker_projectname() -> str:
    return f'{os.environ[ENVVAR_PROJECT_PROJNAME]}-{os.environ[ENVVAR_PROJECT_ENVNAME]}'.lower() # todo: Project names must contain only lowercase letters, decimal digits, dashes, and underscores, and must begin with a lowercase letter or decimal digit

def validate_environment_config(envname: str):
    """ Validates the existence of the specified environment configuration and returns its directory """
    envdir = f"environments/{envname}"
    print(f"looking for $envname environment configuration in {envdir}...") 
    if (not os.path.exists(envdir)):
        raise ToolScriptError(f"No configuration directory found in environments for: {envname}")
    return envdir

def get_current_version():
    """ gets the current version from the version file """
    version = None
    with open("software_version", "r") as f:
        version = semantic_version.Version(f.read())
    return version

def cleanup_for_build():
    buildenv = os.environ[ENVVAR_PROJECT_ENVNAME]
    envdir = validate_environment_config(buildenv)

    print(f"cleaning up any current instances of version {os.environ[ENVVAR_PROJECT_TARGET_SOFTWAREVERSION]}")

    # Figure out what images I'm building
    image_exlusions = ['mysql:latest']
    build_images = []

    with open("docker-compose.yml", "r") as stream:
        yml = yaml_env.load(stream, False)
        for sk, service in yml['services'].items():
            if service['image'] not in image_exlusions:
                build_images.append(service['image'])
    
    with open(os.path.join(envdir, "docker-compose.overrides.yml"), "r") as stream:
        yml = yaml_env.load(stream, False)
        for sk, service in yml['services'].items():
            try:
                if service['image'] not in image_exlusions:
                    build_images.append(service['image'])
            except KeyError: # overrides might not have an image node
                pass

    # Figure out if images already exists

    image_data = subprocess.run(["docker", "image", "ls", "--format", "'{{json .}}'"], capture_output=True).stdout

    existing_images  = list(filter(lambda z: z in build_images, map(lambda y: f'{y["Repository"]}:{y["Tag"]}', map(lambda x: json.loads(x[1:-1]), filter( len, image_data.split(bytes([10])))))))

    # Figure out if there are projects that use those images

    projects = json.loads(subprocess.run(["docker", "compose", "ls", "--format", "json", "--all"], capture_output=True).stdout)

    projects_to_delete = []

    for project in projects:
        projectname = project["Name"]
        os.environ[ENVVAR_PROJECT_ENVNAME] = projectname
        project_data = subprocess.run(["docker", "compose", "-p",  projectname, "ps",  "-a", "--format", "json"], capture_output=True).stdout
        project_containers = json.loads(format_json(project_data))
        for container in project_containers:
            if container["Image"] in existing_images:
                projects_to_delete.append(projectname)
                break

    # stop and delete the projects

    for projectname in projects_to_delete:
        os.environ[ENVVAR_PROJECT_ENVNAME] = projectname
        subprocess.run(["docker", "compose", "-p",  projectname, "down"])

    # remove images

    for image in existing_images:
        subprocess.run(["docker", "image", "rm",  image])

    os.environ[ENVVAR_PROJECT_ENVNAME] = buildenv

def build():
    envname = os.environ[ENVVAR_PROJECT_ENVNAME]
    envdir = validate_environment_config(envname)

    print(f"building with environment config: {envname}")
    compose_result = subprocess.run(["docker", "compose", 
                    "-f", "docker-compose.yml", 
                    "-f", f"{envdir}/docker-compose.overrides.yml",
                    "build",
                    "--progress", "plain"])
    
    if compose_result.returncode != 0:
        raise ToolScriptError(f'build failed, exit code: {compose_result.returncode}')
    
def compose_down_env():
    docker_project = get_docker_projectname()
    subprocess.run(["docker", "compose", "-p",  docker_project, "down"])
    
def compose_env(cleanup = True):
    if cleanup:
        compose_down_env()

    envname = os.environ[ENVVAR_PROJECT_ENVNAME]
    envdir = validate_environment_config(envname)

    print(f"Composing environment: {envname}")

    command = ["docker", "compose",
                    "-f", "docker-compose.yml"]

    overrides_file = f"{envdir}/docker-compose.overrides.yml"
    if os.path.exists(overrides_file):
        command.extend(["-f", overrides_file])
        print(f"found compose overrides yaml file: {overrides_file}")

    docker_project = get_docker_projectname()

    command.extend(["--project-name", f"{docker_project}",
                    "up",
                    "-d",])

    compose_result = subprocess.run(command)
    
    if compose_result.returncode != 0:
        raise ToolScriptError(f'compose failed, exit code: {compose_result.returncode}')
    
def format_json(data: bytes):
    """ developers at docker can't fucking decide how to output their json data https://github.com/docker/compose/issues/10958 """
    sep = b"}\n{"
    if data.find(sep) >= 0: # this happens on linux. the data is a series of json objects separated by newlines insetad of being wrapped into a json array. we need to make it an actually valid json manually, happy times
        return b"["+data.replace(sep, b"},{")+b"]"
    else: # this currently happens on windows, probably because it's a bit behind with updates
        return data