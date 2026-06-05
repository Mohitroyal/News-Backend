import os
file_path = 'app/services/render_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''                const paragraphs = [...data.sections];
                if (paragraphs.length > 0 && data.dateline) {'''

new_block = '''                const paragraphs = [...data.sections];
                const originalParagraphs = [...data.sections];
                if (paragraphs.length > 0 && data.dateline) {'''

if old_block in content:
    content = content.replace(old_block, new_block)
else:
    print('Failed 1')

old_block2 = '''                let currentRegionIdx = 0;
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

new_block2 = '''                let currentRegionIdx = 0;
                let activeRegion = regions[currentRegionIdx];
                let fits = true;
                let flowingOriginal = true;
                let fillerRemainder = "";
                
                while (activeRegion) {
                    if (pIdx >= paragraphs.length) {
                        flowingOriginal = false;
                    }
                    
                    let text = "";
                    if (flowingOriginal) {
                        text = paragraphs[pIdx];
                    } else {
                        // Filler system: duplicate content to guarantee 95%+ utilization
                        text = fillerRemainder || originalParagraphs[(pIdx - originalParagraphs.length) % originalParagraphs.length];
                    }'''

if old_block2 in content:
    content = content.replace(old_block2, new_block2)
else:
    print('Failed 2')


old_block3 = '''                        const remainingText = words.slice(wIdx).join(' ');
                        if (remainingText.trim().length > 0) {
                            if (flowingOriginal) {
                                paragraphs.splice(pIdx, 1, remainingText);
                            } else {
                                pIdx++;
                            }
                        } else {
                            pIdx++;
                        }'''

new_block3 = '''                        const remainingText = words.slice(wIdx).join(' ');
                        if (remainingText.trim().length > 0) {
                            if (flowingOriginal) {
                                paragraphs.splice(pIdx, 1, remainingText);
                            } else {
                                fillerRemainder = remainingText;
                            }
                        } else {
                            if (!flowingOriginal) {
                                fillerRemainder = "";
                            }
                            pIdx++;
                        }'''

if old_block3 in content:
    content = content.replace(old_block3, new_block3)
else:
    print('Failed 3')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
