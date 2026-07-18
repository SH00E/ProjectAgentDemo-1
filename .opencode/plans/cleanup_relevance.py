import re

path = 'repair_agent/ui/static/app.js'
with open(path, encoding='utf-8') as f:
    text = f.read()

# Remove ALL lines with relevance variable declarations
text = re.sub(r"^\s*const relevance = [^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^\s*const relevanceClass = [^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^\s*let relevanceClass = [^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^\s*let relevanceLabel = [^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^\s*if \(relevance === [^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^\s*relevanceClass = [^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^\s*relevanceLabel = [^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^\s*\} else if \(relevance === [^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^\s*\}\s*\n", "", text, flags=re.MULTILINE)

# Remove relevance from evidenceData objects
text = re.sub(r"\s*relevance: relevance,\s*\n", "\n", text)

# Remove relevance-badge spans
text = re.sub(r"\s*<span class=\"relevance-badge[^>]*>[^<]*</span>\n", "\n", text)

# Remove relevance detail in modal
text = re.sub(r"\s*if \(data\.relevance\) \{[^}]*\}\s*\n", "\n", text)
text = re.sub(r"\s*<div class=\"detail-label\">[^<]*</div>\s*\n", "", text)
text = re.sub(r"\s*<div class=\"detail-value\">\s*\n\s*<span class=\"detail-relevance[^>]*>[^<]*</span>\s*\n\s*</div>\s*\n", "\n", text)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Done - aggressive clean')
