import os
import sys

import packaging.version

sys.path.insert(0, os.path.abspath('../src'))

import linesieve  # noqa: E402


project = 'linesieve'
copyright = '2022, lemon24'
author = 'lemon24'

version = packaging.version.parse(linesieve.__version__).base_version
release = linesieve.__version__


extensions = [
    'sphinx_rtd_theme',
]


html_theme = 'sphinx_rtd_theme'


import docutils.nodes  # noqa: E402
import sphinx_click.ext  # noqa: E402


class ClickDirective(sphinx_click.ext.ClickDirective):

    """sphinx_click transforms \b paragraphs into line blocks.
    We transform them back into literal blocks.

    """

    def run(self, *args, **kwargs):
        rv = list(super().run(*args, **kwargs))

        def transform(node):
            lines = [n for n in node.findall(lambda n: n.tagname == 'line')]
            indent = min(line.indent for line in lines)
            rawsource = '\n'.join(
                ' ' * (line.indent - indent) + line.rawsource for line in lines
            )
            return docutils.nodes.literal_block(
                rawsource, docutils.nodes.Text(rawsource), indent=indent
            )

        def recurse(nodes):
            for i, node in enumerate(list(nodes)):
                if node.tagname == 'line_block':
                    nodes[i] = transform(node)
                    continue
                recurse(node.children)

        recurse(rv)

        return rv


def setup(app):
    app.add_directive('click', ClickDirective)
