#!/bin/bash
# Script to run the Dockerfile

# Load environment variables
if [ -f .env ]; then
    source .env
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Please set the ANTHROPIC_API_KEY environment variable."
    exit 1
fi

echo "Your ANTHROPIC_API_KEY is: $ANTHROPIC_API_KEY"

existing_image=$(docker images -q computer-use-demo:local)
if [ -z "$existing_image" ]; then
    # Build the Docker image
    docker build . -t computer-use-demo:local
fi

# Run the Docker container
docker run \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v $(pwd):/home/computeruse/computer_use_demo/ \
    -v $HOME/.anthropic:/home/computeruse/.anthropic \
    -p 5900:5900 \
    -p 8501:8501 \
    -p 6080:6080 \
    -p 8080:8080 \
    -it computer-use-demo:local