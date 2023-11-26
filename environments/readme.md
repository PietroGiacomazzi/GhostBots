An environment is defined by an environment folder with the same name

inside the env folder, we need to have:
 - A secrets folder containing secret files that are referenced in the main docker compose file
 - A docker-compose.overrides.yml defining volumes and any environment specific differences
 - A config.ini file for the application that will be mounted