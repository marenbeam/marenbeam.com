#!/usr/bin/python3

import panflute

def action(elem, doc):
    if isinstance(elem, panflute.Header):
        if elem.level == 1:
            text = panflute.stringify(elem)
            rainbow_header = '<h1 id="' + text + '">' + rainbowify(text) + '</h1>'
            return(panflute.RawBlock(rainbow_header))

def rainbowify(text):
    colors = ['<span style="color:#ff0000">', '<span style="color:#00ff00">', '<span style="color:#ffff00">', '<span style="color:#0000ff">', '<span style="color:#ff00ff">', '<span style="color:#00ffff">']
    end_span = '</span>'

    color = 0
    rainbow_text = ''

    for letter in text:
        if letter != ' ':
            new_text = colors[color] + letter + end_span
            if color == len(colors)-1:
                color = 0
            else:
                color += 1
        else:
            new_text = ' '

        rainbow_text += new_text

    return rainbow_text

if __name__ == '__main__':
    panflute.run_filter(action)
