#!/bin/bash

# Workload Identity Federation Setup Script for GitHub Actions
# This is more secure than service account keys and is Google's recommended approach

set -e

# Configuration
PROJECT_ID="novalark-prod"
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
SERVICE_ACCOUNT_NAME="github-actions"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
POOL_ID="github-actions-pool"
PROVIDER_ID="github-actions-provider"
REPO_OWNER="TaylorFinklea"  # TODO: Replace with your actual GitHub username/org
REPO_NAME="simple_explainations"         # TODO: Replace with your actual repo name

echo "🔐 Setting up Workload Identity Federation for GitHub Actions"
echo "=============================================================="
echo "Project: ${PROJECT_ID}"
echo "Project Number: ${PROJECT_NUMBER}"
echo "Service Account: ${SERVICE_ACCOUNT_EMAIL}"
echo "Repository: ${REPO_OWNER}/${REPO_NAME}"
echo ""

# Check if user is logged in
echo "🔍 Checking authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Please run 'gcloud auth login' first"
    exit 1
fi

# Set the project
echo "📋 Setting project..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable iam.googleapis.com
gcloud services enable iamcredentials.googleapis.com

# Create service account if it doesn't exist
echo "👤 Creating service account..."
if gcloud iam service-accounts describe ${SERVICE_ACCOUNT_EMAIL} >/dev/null 2>&1; then
    echo "ℹ️  Service account already exists"
else
    echo "Creating new service account..."
    if gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} \
        --description="GitHub Actions deployment for AI Word Prediction" \
        --display-name="GitHub Actions"; then
        echo "✅ Service account created successfully"
    else
        echo "❌ Failed to create service account"
        exit 1
    fi
fi

# Grant permissions to service account
echo "🔐 Granting permissions to service account..."

# Function to add IAM policy binding with error checking
add_iam_binding() {
    local role=$1
    echo "  Adding role: $role"
    if gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
        --role="$role" >/dev/null 2>&1; then
        echo "    ✅ Added $role"
    else
        echo "    ⚠️  Warning: Failed to add $role (may already exist or insufficient permissions)"
    fi
}

# Add all required roles
add_iam_binding "roles/cloudbuild.builds.editor"
add_iam_binding "roles/run.admin"
add_iam_binding "roles/storage.admin"
add_iam_binding "roles/artifactregistry.writer"
add_iam_binding "roles/iam.serviceAccountUser"

# Create Workload Identity Pool
echo "🏊 Creating Workload Identity Pool..."
if gcloud iam workload-identity-pools describe ${POOL_ID} \
    --location="global" >/dev/null 2>&1; then
    echo "ℹ️  Workload Identity Pool already exists"
else
    gcloud iam workload-identity-pools create ${POOL_ID} \
        --location="global" \
        --description="GitHub Actions pool for AI Word Prediction" \
        --display-name="GitHub Actions Pool"
    echo "✅ Workload Identity Pool created"
fi

# Create Workload Identity Provider
echo "🔗 Creating Workload Identity Provider..."
if gcloud iam workload-identity-pools providers describe ${PROVIDER_ID} \
    --workload-identity-pool=${POOL_ID} \
    --location="global" >/dev/null 2>&1; then
    echo "ℹ️  Workload Identity Provider already exists"
else
    gcloud iam workload-identity-pools providers create-oidc ${PROVIDER_ID} \
        --workload-identity-pool=${POOL_ID} \
        --location="global" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
        --attribute-condition="assertion.repository=='${REPO_OWNER}/${REPO_NAME}'"
    echo "✅ Workload Identity Provider created"
fi

# Allow GitHub Actions to impersonate the service account
echo "🤝 Binding GitHub Actions to service account..."
gcloud iam service-accounts add-iam-policy-binding ${SERVICE_ACCOUNT_EMAIL} \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO_OWNER}/${REPO_NAME}"

# Get the Workload Identity Provider resource name
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo ""
echo "✅ Workload Identity Federation setup complete!"
echo "=============================================="
echo ""
echo "📋 GitHub Repository Secrets to add:"
echo "------------------------------------"
echo ""
echo "1. Go to: https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/secrets/actions"
echo ""
echo "2. Add these secrets:"
echo ""
echo "   Secret name: WIF_PROVIDER"
echo "   Secret value: ${WIF_PROVIDER}"
echo ""
echo "   Secret name: WIF_SERVICE_ACCOUNT"
echo "   Secret value: ${SERVICE_ACCOUNT_EMAIL}"
echo ""
echo "   Secret name: GCP_PROJECT_ID"
echo "   Secret value: ${PROJECT_ID}"
echo ""
echo "🔧 Update the GitHub Action workflow to use these values:"
echo "--------------------------------------------------------"
echo ""
echo "Replace the auth step in .github/workflows/deploy-ai-app.yml with:"
echo ""
echo "      - name: Google Auth"
echo "        id: auth"
echo "        uses: google-github-actions/auth@v2"
echo "        with:"
echo "          workload_identity_provider: \${{ secrets.WIF_PROVIDER }}"
echo "          service_account: \${{ secrets.WIF_SERVICE_ACCOUNT }}"
echo ""
echo "And remove the 'credentials_json' line completely."
echo ""
echo "🚀 After adding the secrets, your GitHub Actions will automatically"
echo "   authenticate using Workload Identity Federation (no keys needed)!"
echo ""
echo "🔒 Security benefits:"
echo "   - No long-lived service account keys"
echo "   - Automatic token rotation"
echo "   - Repository-specific access"
echo "   - Audit trail of all authentication"
echo ""
echo "⚠️  Important: Update REPO_OWNER and REPO_NAME variables in this script"
echo "   if they don't match your actual GitHub repository!"
