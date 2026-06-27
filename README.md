# Automating HR with Agents
MVP for automating the initial screenings of HR processes (Mostly outside white collar jobs) with stateful agents and human in the loop for the important stuff. This project can make use of an OpenAI token to be ran but its designed to run in a local opensource stack for sensitive PII handling and avoiding lock in.

## Structure 

This repository is structured using MLOps principles and patterns first being the directory structure:

1. **production/**: API + UI for ease of usage and scaling to production.
2. **docs/**:
3.

## Stack
This project is designed to be ran fully on premise and opensource but also with the possibility of using external LLM providers (OpenAI, Anthropic, DeepSeek...) for deployments with out on-premise gpu's. The tech stack has been selected following the principle of less complexity first (More on it on docs/design-tradeoffs.md):

## Install

In order to fully reproduce and run this project you can either opt out for local installation of a fresh environment or docker installation.

### Local installation

```python 
brew install pyenv # For mac
sudo apt install 
pyenv install 3.13.0
pyenv virtualenv 3.13.0 hr
pyenv activate hr
pyenv local hr
pip install -r requirements.
``` 

### Docker installation


## Usage


```

```
## License & Authors

This project has been singlehandedly made by Walter Troiani, but special thanks to all the contributors of the open source packages used throughout the project.

This project is licensed under Apache 2.0.

