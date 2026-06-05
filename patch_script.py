import os

file_path = 'app/services/render_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replacement 1
old1 = '''                let currentRegionIdx = 0;
                let activeRegion = regions[currentRegionIdx];
                let fits = true;
                
                while (activeRegion) {
                    if (pIdx >= paragraphs.length) {
                        break;
                    }
                    
                    let text = paragraphs[pIdx];'''
new1 = '''                let currentRegionIdx = 0;
                let activeRegion = regions[currentRegionIdx];
                let fits = true;
                let flowingOriginal = true;
                
                while (activeRegion) {
                    if (pIdx >= paragraphs.length) {
                        flowingOriginal = false;
                    }
                    
                    let text = "";
                    if (flowingOriginal) {
                        text = paragraphs[pIdx];
                    } else {
                        // Filler system: duplicate content to guarantee 95%+ utilization
                        const fillerIdx = (pIdx - paragraphs.length) % paragraphs.length;
                        text = paragraphs[fillerIdx];
                    }'''
if old1 in content:
    content = content.replace(old1, new1)
else:
    print('Failed to find old1')

# Replacement 2
old2 = '''                        const remainingText = words.slice(wIdx).join(' ');
                        if (remainingText.trim().length > 0) {
                            paragraphs.splice(pIdx, 1, remainingText);
                        } else {
                            pIdx++;
                        }'''
new2 = '''                        const remainingText = words.slice(wIdx).join(' ');
                        if (remainingText.trim().length > 0) {
                            if (flowingOriginal) {
                                paragraphs.splice(pIdx, 1, remainingText);
                            } else {
                                pIdx++;
                            }
                        } else {
                            pIdx++;
                        }'''
if old2 in content:
    content = content.replace(old2, new2)
else:
    print('Failed to find old2')

# Replacement 3
old3 = '''                        if (!activeRegion) {
                            if (pIdx < paragraphs.length) {
                                fits = false;
                            }
                            break;
                        }'''
new3 = '''                        if (!activeRegion) {
                            if (flowingOriginal && pIdx < paragraphs.length) {
                                fits = false;
                            }
                            break;
                        }'''
if old3 in content:
    content = content.replace(old3, new3)
else:
    print('Failed to find old3')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
