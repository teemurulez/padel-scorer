# PythonAnywhere Deployment Guide

Step-by-step guide to deploy Padel Paroni on PythonAnywhere.

---

## Step 1: Create a PythonAnywhere Account

1. Go to https://www.pythonanywhere.com
2. Click "Pricing & signup"
3. Choose **"Create a Beginner account"** (free) or **"Hacker"** ($5/month for custom domain)
4. Fill in username, email, password
5. Verify your email

---

## Step 2: Upload Your Code

### Option A: Using Git (Recommended)

1. On PythonAnywhere, click **"Consoles"** tab
2. Start a **"Bash"** console
3. Run these commands:
   ```bash
   git clone https://github.com/YOUR_USERNAME/tennis-scorer.git
   cd tennis-scorer
   ```

### Option B: Upload ZIP file

1. On your computer, create a ZIP of your project folder (exclude `venv/` folder)
2. On PythonAnywhere, click **"Files"** tab
3. Click "Upload a file" and upload the ZIP
4. Open a Bash console and run:
   ```bash
   unzip tennis-scorer.zip
   cd tennis-scorer
   ```

---

## Step 3: Set Up Virtual Environment

In the Bash console, run:

```bash
cd tennis-scorer
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Wait for all packages to install (this takes a few minutes).

---

## Step 4: Set Up the Database

The app automatically creates the database on first run. You have two options:

### Option A: Start Fresh (new database)
Just continue to the next step - the database will be created automatically when the app starts.

### Option B: Use Your Existing Data
1. Go to **"Files"** tab on PythonAnywhere
2. Navigate to your project folder
3. Create folder: `instance` (if it doesn't exist)
4. Upload your `instance/padel.db` file into that folder

---

## Step 5: Create Web App

1. Go to **"Web"** tab
2. Click **"Add a new web app"**
3. Click "Next" (accept the free domain `yourusername.pythonanywhere.com`)
4. Select **"Manual configuration"** (NOT Flask)
5. Select **Python 3.9**
6. Click "Next"

---

## Step 6: Configure the Web App

On the Web tab, fill in these settings:

### Source code
```
/home/YOUR_USERNAME/tennis-scorer
```

### Working directory
```
/home/YOUR_USERNAME/tennis-scorer
```

### Virtualenv
```
/home/YOUR_USERNAME/tennis-scorer/venv
```

---

## Step 7: Edit WSGI File

1. On the Web tab, click the link to your **WSGI configuration file**
   (something like `/var/www/yourusername_pythonanywhere_com_wsgi.py`)

2. Delete ALL the existing content

3. Paste this code:

```python
import sys
import os

# Add your project directory to the path
project_home = '/home/YOUR_USERNAME/tennis-scorer'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['SECRET_KEY'] = 'YOUR_SECRET_KEY_HERE'

# Import your Flask app
from app import app as application
```

4. **IMPORTANT:** Replace:
   - `YOUR_USERNAME` with your PythonAnywhere username
   - `YOUR_SECRET_KEY_HERE` with a secure random key (see below)

### Generate a Secret Key

On your computer or in PythonAnywhere console, run:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as your SECRET_KEY.

---

## Step 8: Reload and Test

1. Go back to the **Web** tab
2. Click the green **"Reload"** button
3. Click on your web app link (e.g., `yourusername.pythonanywhere.com`)
4. Your app should be running!

---

## Troubleshooting

### "Something went wrong" error

1. Go to Web tab
2. Click "Error log" link
3. Look at the last few lines to see what went wrong

### Common issues:

**Module not found:**
- Make sure virtualenv path is correct
- Try reinstalling: `pip install -r requirements.txt`

**Database errors:**
- Check that `instance/padel.db` exists
- Check file permissions

**500 error:**
- Check error log
- Make sure SECRET_KEY is set

---

## Updating the App

When you make changes:

1. Open Bash console on PythonAnywhere
2. Run:
   ```bash
   cd tennis-scorer
   git pull  # if using git
   source venv/bin/activate
   pip install -r requirements.txt  # if dependencies changed
   ```
3. Go to Web tab and click **"Reload"**

---

## Custom Domain (Optional, requires paid plan)

1. Upgrade to Hacker plan ($5/month)
2. Go to Web tab
3. Add your domain in "Custom domains" section
4. Update your domain's DNS to point to PythonAnywhere (they provide instructions)

---

## Database Backups

Your database is at `/home/YOUR_USERNAME/tennis-scorer/instance/padel.db`

To download a backup:
1. Go to Files tab
2. Navigate to `tennis-scorer/instance/`
3. Click on `padel.db` to download

Or use the app's built-in backup feature in Admin > Data tab.
