# HR Agent
A small MVP for a computer vision pipeline that is able to recognize and extract objects from a picture, extract barcodes, read them and associate each barcode with each object.

## Structure 

This repository is structured using MLOps principles and patterns first, so this is the reason behind the split of **research/**, **src/** and **production** which showcases a final demonstration of the product. The directory structure is:

1. **production/**: API + UI for ease of usage and scaling to production.
2. **src/**: Modular source code to use for production, ready for deployment as a PyPI library
3. **research/**: Notebooks, scripts and other artifacts dedicated to research and fast iteration.

## Install

In order to fully reproduce and run this project you can either opt out for local installation of a fresh environment or docker installation.

### Local installation

```python 
brew install pyenv # For mac
pyenv install 3.13.12
pyenv virtualenv 3.13.12 barcodes 
pyenv activate barcodes
pyenv local barcodes
pip install -r requirements.
python -m ipykernel install --user --name=$(basename $VIRTUAL_ENV)
``` 

Depending on the tool used for jupyter you will need plumbing of the python interpreter path if it doesn't pop out automatically, which will be something like:

```
~/.pyenv/versions/barcodes/bin/python
```

### Docker installation


## Usage


```

```
## License & Authors

This project has been singlehandedly made by Walter Troiani, but special thanks to the research team of DINO for the great self-supervised model and to Sobel for the great filters :)

This project is licensed under Apache 2.0.

## Next Steps / Ideas / WIP

- Small LLM to act as textual UI for the user (Not enough compute on my laptop), even a small Qwen 3 0.6B would suffice for this task.

- 
