#!/bin/bash

# Set variables
ACR_NAME="Coach"
REPOSITORY="development"
KEEP_TAG="0.1.0"

# Get all tags for the repository
tags=$(az acr repository show-tags --name $ACR_NAME --repository $REPOSITORY --output tsv)

# Loop through tags and delete those that don't match KEEP_TAG
for tag in $tags
do
    if [ "$tag" != "$KEEP_TAG" ]; then
        echo "Deleting tag: $tag"
        az acr repository delete --name $ACR_NAME --image "$REPOSITORY:$tag" --yes
    else
        echo "Keeping tag: $tag"
    fi
done


echo "Tag deletion process completed."
