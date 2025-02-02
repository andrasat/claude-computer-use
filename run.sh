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

existing_image=$(docker images -q claude-comp-use:local)
if [ -z "$existing_image" ]; then
    # Build the Docker image
    docker build . -t claude-comp-use:local || exit 1
fi

# Remove existing container
docker rm -f comp-use

# Run the Docker container
docker run \
    --rm \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v $(pwd):/home/computeruse/app/ \
    -v $HOME/.anthropic:/home/computeruse/app/.anthropic \
    --name comp-use \
    -it claude-comp-use:local \
    /bin/bash