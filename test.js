const fs = require('fs');
const html = fs.readFileSync('test_syntax.html', 'utf8');
const { JSDOM } = require('jsdom');
const dom = new JSDOM(html, { runScripts: 'dangerously' });
dom.window.document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        console.log('Layout Done:', dom.window.__LAYOUT_DONE__);
        console.log('Master Block:', !!dom.window.document.querySelector('.nc-editorial-master'));
        console.log('Hero Float:', dom.window.document.querySelector('.nc-hero-img-wrapper')?.style.float);
    }, 100);
});

