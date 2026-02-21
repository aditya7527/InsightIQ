import os

css_path = r"c:\Users\ASUS\Desktop\Inside\app\static\style.css"

with open(css_path, "a", encoding="utf-8") as f:
    f.write("""

/* ========== ABSOLUTE FORECAST OVERRIDE ========== */
html body #forecast-section {
  background-color: #ffffff !important;
  background: #ffffff !important;
  border-radius: 12px !important;
  padding: 24px !important;
  margin-top: 2rem !important;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
  border: 1px solid #e2e8f0 !important;
  position: relative !important;
  z-index: 9999 !important;
  display: block !important;
  opacity: 1 !important;
}

html body #forecast-section * {
  color: #1e293b !important;
  text-shadow: none !important;
}

html body #forecast-section .section-subtitle {
  color: #64748b !important;
}
""")

print("style.css updated with high-specificity override.")
