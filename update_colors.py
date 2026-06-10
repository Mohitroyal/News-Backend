import re

with open('src/index.css', 'r', encoding='utf-8') as f:
    css = f.read()

theme_block = '''@theme {
  --color-ink-black: #0d1b2a;
  --color-prussian-blue: #1b263b;
  --color-dusk-blue: #415a77;
  --color-dusty-denim: #778da9;
  --color-alabaster-grey: #e0e1dd;
}
'''

if '@theme' not in css:
    css = css.replace('@import "tailwindcss";', '@import "tailwindcss";\n' + theme_block)

css = css.replace('dark:bg-gray-900', 'dark:bg-ink-black')
css = css.replace('dark:text-gray-100', 'dark:text-alabaster-grey')

with open('src/index.css', 'w', encoding='utf-8') as f:
    f.write(css)

with open('src/screens/GenerateScreen.tsx', 'r', encoding='utf-8') as f:
    tsx = f.read()

tsx = tsx.replace('dark:bg-gray-900', 'dark:bg-ink-black')
tsx = tsx.replace('dark:bg-gray-800', 'dark:bg-prussian-blue')
tsx = tsx.replace('dark:bg-gray-700/50', 'dark:bg-dusk-blue/50')
tsx = tsx.replace('dark:bg-gray-700', 'dark:bg-dusk-blue')

tsx = tsx.replace('dark:border-gray-800', 'dark:border-prussian-blue')
tsx = tsx.replace('dark:border-gray-700', 'dark:border-dusk-blue')
tsx = tsx.replace('dark:border-gray-600', 'dark:border-dusty-denim')

tsx = tsx.replace('dark:text-white', 'dark:text-alabaster-grey')
tsx = tsx.replace('dark:text-gray-300', 'dark:text-alabaster-grey')
tsx = tsx.replace('dark:text-gray-400', 'dark:text-dusty-denim')
tsx = tsx.replace('dark:text-gray-500', 'dark:text-dusty-denim')

with open('src/screens/GenerateScreen.tsx', 'w', encoding='utf-8') as f:
    f.write(tsx)

print('Done')
