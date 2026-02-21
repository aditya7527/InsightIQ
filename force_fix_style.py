import os

css_path = r"c:\Users\ASUS\Desktop\Inside\app\static\style.css"

with open(css_path, "rb") as f:
    content = f.read()

# Decode with replacement to handle any binary garbage
text = content.decode("utf-8", errors="replace")

# Locate the safe truncation point: Closing brace of .hero-badge
marker = ".hero-badge"
idx = text.find(marker)

if idx == -1:
    print("Error: Could not find .hero-badge marker. Aborting.")
    exit(1)

# Find closing brace of .hero-badge
end_brace = text.find("}", idx)
if end_brace == -1:
    print("Error: Could not find closing brace for .hero-badge. Aborting.")
    exit(1)

# Keep content up to closing brace
clean_content = text[:end_brace+1]

# New CSS to append
new_css = """

/* ========== HERO TITLE GRADIENT ========== */
.hero-title-gradient {
  background: linear-gradient(to right, #a855f7, #6366f1, #3b82f6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent !important;
  width: fit-content;
  margin-left: auto;
  margin-right: auto;
  text-shadow: none !important;
}

/* ========== FORECAST SECTION OVERRIDE ========== */
#forecast-section {
  background: white !important;
  border-radius: 12px !important;
  padding: 24px !important;
  margin-top: 2rem !important;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
  border: 1px solid #e2e8f0 !important;
  position: relative;
  z-index: 10;
}

#forecast-section h2, 
#forecast-section h3, 
#forecast-section .section-title,
#forecast-section p, 
#forecast-section label {
  color: #1e293b !important; /* Slate-800 for high contrast */
  text-shadow: none !important;
}

#forecast-section .section-subtitle {
  color: #64748b !important; /* Slate-500 for subtitle */
  text-shadow: none !important;
}
"""

final_text = clean_content + new_css

with open(css_path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("style.css forcefully rewritten and cleaned.")
