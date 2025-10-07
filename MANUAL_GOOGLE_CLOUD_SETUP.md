# Manual Google Cloud Setup (No CLI Required)

If you don't want to use the gcloud CLI, you can set up using the web console.

## Step 1: Create Google Cloud Project

1. Go to: https://console.cloud.google.com/
2. Click "Select a project" → "New Project"
3. Name it: `prompt-optimization`
4. Click "Create"
5. Note your **Project ID** (e.g., `prompt-optimization-123456`)

## Step 2: Enable Vertex AI API

1. Go to: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com
2. Make sure your project is selected at the top
3. Click "Enable"
4. Wait for activation (~30 seconds)

## Step 3: Create Service Account Key

1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Click "Create Service Account"
3. Name: `prompt-optimizer`
4. Click "Create and Continue"
5. Role: Select "Vertex AI User"
6. Click "Continue" → "Done"
7. Click on the new service account
8. Go to "Keys" tab
9. Click "Add Key" → "Create new key"
10. Choose "JSON"
11. Download the key file to: `c:\Users\panik\Documents\GitHub\Protcol2USDMv3\google-cloud-key.json`

## Step 4: Install Python Packages

```powershell
pip install google-cloud-aiplatform vertexai
```

## Step 5: Update .env File

Add these lines to your `.env` file:

```bash
# Google Cloud for Prompt Optimization
GOOGLE_CLOUD_PROJECT=your-project-id-here
GOOGLE_APPLICATION_CREDENTIALS=google-cloud-key.json
GOOGLE_CLOUD_LOCATION=us-central1
```

Replace `your-project-id-here` with your actual Project ID from Step 1.

## Step 6: Test Setup

```powershell
python test_optimizer.py
```

You should see:
```
✅ PASS: Vertex AI Connection
Results: 5/5 tests passed
```

## Done!

You can now use prompt optimization:

```powershell
# Test optimization
python prompt_optimizer.py "Your prompt" --method google-zeroshot

# Run benchmark with optimization
python benchmark_prompts.py --test-set test_data\ --auto-optimize
```

---

## Security Note

⚠️ **IMPORTANT**: The service account key file contains credentials.

- Do NOT commit `google-cloud-key.json` to git
- Add it to `.gitignore`
- Keep it secure

The file is already in `.gitignore` by default.
