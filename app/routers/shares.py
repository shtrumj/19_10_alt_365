"""
Shares router for serving Outlook troubleshooting files
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
import os
from pathlib import Path

router = APIRouter(tags=["shares"])

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

@router.get("/test")
async def shares_test():
    """Test endpoint"""
    return {"message": "Shares router is working", "status": "success", "timestamp": "2025-09-30T21:10:00Z"}

@router.get("/")
async def shares_index(request: Request):
    """Shares index page"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Outlook Troubleshooting Files</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        .file-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            background: #f9f9f9;
        }
        .file-card h3 {
            margin-top: 0;
            color: #0066cc;
        }
        .file-card p {
            color: #666;
            margin-bottom: 15px;
        }
        .download-btn {
            background: #0066cc;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 4px;
            display: inline-block;
            margin-right: 10px;
        }
        .download-btn:hover {
            background: #0052a3;
        }
        .view-btn {
            background: #28a745;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 4px;
            display: inline-block;
        }
        .view-btn:hover {
            background: #218838;
        }
        .icon {
            font-size: 24px;
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 Outlook Troubleshooting Files</h1>
        
        <div class="file-card">
            <h3><span class="icon">📖</span>Outlook 2021 Setup Guide</h3>
            <p>Complete step-by-step guide for setting up Outlook 2021 with our Exchange server. Includes registry fixes, autodiscover configuration, and troubleshooting steps.</p>
            <a href="/shares/outlook-2021-setup-guide" class="download-btn">📥 Download Guide</a>
            <a href="/shares/outlook-2021-setup-guide.html" class="view-btn">👁️ View Online</a>
        </div>
        
        <div class="file-card">
            <h3><span class="icon">📄</span>Local Autodiscover XML</h3>
            <p>Backup autodiscover XML file for manual configuration. Use this if automatic autodiscover fails or for offline setup.</p>
            <a href="/shares/outlook-2021-local-autodiscover" class="download-btn">📥 Download XML</a>
            <a href="/shares/outlook-2021-local-autodiscover.xml" class="view-btn">👁️ View XML</a>
        </div>
        
        <div class="file-card">
            <h3><span class="icon">🔧</span>Registry Fix for Outlook 2021</h3>
            <p>Basic Windows registry fix to prevent Outlook 2021 from trying Office 365 endpoints first. Critical for custom Exchange server setup.</p>
            <a href="/shares/outlook-2021-registry-fix" class="download-btn">📥 Download .reg</a>
        </div>
        
        <div class="file-card">
            <h3><span class="icon">⚙️</span>Enhanced Registry Fix for Outlook 2021</h3>
            <p>Comprehensive registry fix that addresses MAPI HTTP issues and forces Outlook 2021 to use custom Exchange servers. Recommended for persistent connection problems.</p>
            <a href="/shares/outlook-2021-registry-fix-enhanced" class="download-btn">📥 Download Enhanced .reg</a>
        </div>
        
        <div class="file-card">
            <h3><span class="icon">🚀</span>Aggressive Registry Fix for Outlook 2021</h3>
            <p>Most aggressive registry fix that completely disables Office 365 integration and forces MAPI over HTTP. Use this if the enhanced fix doesn't work.</p>
            <a href="/shares/outlook-2021-registry-fix-aggressive" class="download-btn">📥 Download Aggressive .reg</a>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: #e7f3ff; border-radius: 8px; border-left: 4px solid #0066cc;">
            <h4 style="margin-top: 0; color: #0066cc;">💡 Usage Instructions</h4>
            <ol>
                <li><strong>Download the Enhanced Registry Fix</strong> (recommended) or basic registry fix and apply it to your Windows machine first</li>
                <li><strong>Download the Setup Guide</strong> and follow the step-by-step instructions</li>
                <li><strong>Use the Local XML</strong> if automatic autodiscover fails</li>
                <li><strong>Restart Outlook</strong> after applying the registry fix</li>
                <li><strong>If still having issues</strong>, try the enhanced registry fix which addresses MAPI HTTP problems</li>
            </ol>
        </div>
    </div>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

@router.get("/outlook-2021-setup-guide")
async def download_setup_guide():
    """Download Outlook 2021 Setup Guide"""
    file_path = PROJECT_ROOT / "OUTLOOK_2021_SETUP_GUIDE.md"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Setup guide not found")
    
    return FileResponse(
        path=str(file_path),
        filename="Outlook_2021_Setup_Guide.md",
        media_type="text/markdown"
    )

@router.get("/outlook-2021-local-autodiscover")
async def download_local_autodiscover():
    """Download Local Autodiscover XML file"""
    file_path = PROJECT_ROOT / "outlook_2021_local_autodiscover.xml"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Local autodiscover XML not found")
    
    return FileResponse(
        path=str(file_path),
        filename="outlook_2021_local_autodiscover.xml",
        media_type="application/xml"
    )

@router.get("/outlook-2021-registry-fix")
async def download_registry_fix():
    """Download Outlook 2021 Registry Fix"""
    file_path = PROJECT_ROOT / "outlook_2021_registry_fix.reg"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Registry fix not found")
    
    return FileResponse(
        path=str(file_path),
        filename="outlook_2021_registry_fix.reg",
        media_type="application/x-msdownload"
    )

@router.get("/outlook-2021-registry-fix-enhanced")
async def download_enhanced_registry_fix():
    """Download Enhanced Outlook 2021 Registry Fix"""
    file_path = PROJECT_ROOT / "outlook_2021_registry_fix_enhanced.reg"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Enhanced registry fix not found")
    
    return FileResponse(
        path=str(file_path),
        filename="outlook_2021_registry_fix_enhanced.reg",
        media_type="application/x-msdownload"
    )

@router.get("/outlook-2021-registry-fix-aggressive")
async def download_aggressive_registry_fix():
    """Download Aggressive Outlook 2021 Registry Fix"""
    file_path = PROJECT_ROOT / "outlook_2021_registry_fix_aggressive.reg"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Aggressive registry fix not found")
    
    return FileResponse(
        path=str(file_path),
        filename="outlook_2021_registry_fix_aggressive.reg",
        media_type="application/x-msdownload"
    )

@router.get("/outlook-2021-setup-guide.html")
async def view_setup_guide(request: Request):
    """View setup guide as HTML"""
    file_path = PROJECT_ROOT / "OUTLOOK_2021_SETUP_GUIDE.md"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Setup guide not found")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Convert markdown to HTML (basic conversion)
        html_content = content.replace('\n', '<br>\n')
        html_content = html_content.replace('# ', '<h1>').replace('\n', '</h1>\n', 1)
        html_content = html_content.replace('## ', '<h2>').replace('\n', '</h2>\n')
        html_content = html_content.replace('### ', '<h3>').replace('\n', '</h3>\n')
        html_content = html_content.replace('**', '<strong>').replace('**', '</strong>')
        html_content = html_content.replace('`', '<code>').replace('`', '</code>')
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Outlook 2021 Setup Guide</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                h1, h2, h3 {{ color: #333; }}
                code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
                strong {{ color: #0066cc; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading setup guide: {str(e)}")

@router.get("/outlook-2021-local-autodiscover.xml")
async def view_local_autodiscover():
    """View local autodiscover XML"""
    file_path = PROJECT_ROOT / "outlook_2021_local_autodiscover.xml"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Local autodiscover XML not found")
    
    return FileResponse(
        path=str(file_path),
        media_type="application/xml"
    )

@router.get("/outlook-2021-registry-fix-force-mapi")
async def download_force_mapi_registry_fix():
    """Download Force MAPI Registry Fix for Outlook 2021"""
    file_path = PROJECT_ROOT / "outlook_2021_registry_fix_force_mapi.reg"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Force MAPI registry fix not found")
    
    return FileResponse(
        path=str(file_path),
        filename="outlook_2021_registry_fix_force_mapi.reg",
        media_type="application/x-msdownload"
    )
