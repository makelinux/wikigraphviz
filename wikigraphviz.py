#!/usr/bin/python3
# -*- coding: utf-8 -*-

r"""
Visualizes category hierarchy.

Generates graphical representation in formats dot, svg and html5
of category hierarchy.

usage: pwb.py graph [-style STYLE] [-depth DEPTH] [-from FROM] [-to TO]

actions:
  -from [FROM]   Category name to scan, default is main category, "?" to ask.

optional arguments:
  -to TO         base file name to save, "?" to ask.
  -style STYLE   graphviz style definitions in dot format:
                 https://graphviz.org/doc/info/attrs.html
  -depth DEPTH   maximal hierarchy depth. 2 by default.
  -downsize K    font size divider for subcategories. 4 by default.
                 Use 1 for the same font size.

Examples:

pwb.py -v category_graph -from
pwb.py category_graph -from Life -downsize 1.5 \
        -style 'graph[rankdir=BT ranksep=0.5] node[shape=circle
        style=filled fillcolor=green] edge[style=dashed penwidth=3]'

"""

import argparse
import io
from collections import defaultdict

import pydot
import pywikibot
from pywikibot import config
from pywikibot.bot import SingleSiteBot

class CategoryGraphBot(SingleSiteBot):
    """Bot to create graph of the category structure."""

    # © 2022 Costa Shulyupin

    def args(self, ap):
        """Declare arguments."""
        ap.add_argument('--style', nargs='?', default='',
                        help='graphviz style definitions in dot format')
        ap.add_argument('-downsize', nargs='?', default=4,
                        help='scaling divider')
        ap.add_argument('--depth', nargs='?', default=2,
                        help='maximal hierarchy depth')
        ap.add_argument('--to', nargs='?', default='',
                        help='base file name to save, "?" to ask')
        ap.add_argument('rest', metavar='...', nargs='?',
                        default='Main topic classifications',
                        help='Category to parse, '
                        'default is main category, "?" to ask')

    def __init__(self, args: argparse.Namespace) -> None:
        """Initialize."""
        super().__init__()
        self.args = args
        cat_title = args.rest
        if cat_title == '?':
            cat_title = pywikibot.input(
                'For which category do you want to create a graph?')
        pywikibot.output('Scanning "{}"'.format(cat_title))
        self.cat = pywikibot.Category(self.site, cat_title)
        self.to = args.to
        if self.to == '?':
            self.to = pywikibot.input(
                'Please enter the name of the file '
                'where the tree should be saved,\n'
                'or press enter to use category name:')
        if not self.to:
            self.to = cat_title.replace(' ', '_')
        self.rev = defaultdict(list)
        self.fw = defaultdict(list)
        self.leaves = set()
        self.counter = 0
        font = 'fontname="Helvetica,Arial,sans-serif"'
        style = 'graph [rankdir=LR ranksep=2 concentrate=true %s] ' \
                'node [newrank=true shape=plaintext %s] ' \
                'edge [arrowhead=open labeldistance=3 ' \
                'labelfontcolor="#00000080" %s] ' \
                % (font, font, font) + args.style
        self.dot = pydot.graph_from_dot_data('digraph {' + style + '}')[0]
        self.dot.set_name('"' + cat_title + '"')

    def scan_level(self, cat, level, hue=None) -> str:
        """
        Recursive function to fill dot graph.

        Parameters:
            * cat - the Category of the node we're currently opening.
            * level - the current decreasing from depth to zero
                      level in the tree (for recursion), opposite of depth.

        """
        title = cat.title(with_ns=False)
        size = float(args.downsize) ** level
        subcats = sorted(cat.subcategories())

        def node():
            subs = ', '.join([c.title(with_ns=False).replace(' ', '&nbsp;')
                              for c in subcats])
            if len(subs) > 1000:
                subs = subs[:1000] + ' ...'
            n = pydot.Node(title,
                           label=r'"{}\n{} C"'.
                           format(title, len(subcats)),
                           tooltip=title + '\n\n' + subs,
                           URL='https://' + self.site.code
                           + '.wikipedia.org/wiki/' + cat.title(as_url=True),
                           fontsize=int(10 * size))
            return n

        def edge(n, h):
            minlen = n % columns + 1 if level != self.args.depth else 1
            e = pydot.Edge(title,
                           subcat.title(with_ns=False),
                           tooltip=title + '  ⟶  '
                           + subcat.title(with_ns=False),
                           headlabel=title,
                           # distribute the graph to depth
                           minlen=minlen,
                           penwidth=round(size / 2, 2),
                           arrowsize=round(size / 4, 2),
                           color=str(round(h, 2)) + ' 1 0.7',
                           labelfontsize=int(size),
                           labelfontcolor=str(round(h, 2)) + ' 1 0.5')
            return e

        if config.verbose_output:
            pywikibot.output('Adding ' + cat.title(with_ns=False))
        node = node()
        self.dot.add_node(node)
        self.counter += 1
        if not level or self.counter >= 1e4:
            # because graphviz crashes on huge graphs
            if self.counter == 1e4:
                pywikibot.warning('Number of nodes reached limit')
            self.leaves.add(node.get_name())
            return
        columns = len(subcats) // 5 + 1
        for n, subcat in enumerate(subcats):
            # generating different hue for color per each root branch
            h = hue if hue is not None else (11 / 18 * n) % 1
            e = edge(n, h)
            self.dot.add_edge(e)
            # repeat recursively
            self.scan_level(subcat, level - 1, h)
            # track graph's structure to reduse too big graph
            self.rev[e.get_destination()].append(e.get_source())
            self.fw[e.get_source()].append(e.get_destination())

    def run(self) -> None:
        """Run main function of CategoryGraphBot."""
        self.scan_level(self.cat, int(self.args.depth))
        # reduce too big graph
        if self.counter > 1000:
            pywikibot.warning('Removing standalone subcategories '
                              'because graph is too big')
            for n in self.leaves:
                while len(self.rev[n]) == 1:
                    if config.verbose_output:
                        pywikibot.output('Removing ' + n)
                    self.dot.del_edge(self.rev[n][0], n)
                    self.dot.del_node(n)
                    self.fw[self.rev[n][0]].remove(n)
                    if self.fw[self.rev[n][0]]:
                        break
                    n = self.rev[n][0]
        pywikibot.output('Saving results')
        pywikibot.output(self.to + '.dot')
        self.dot.write(self.to + '.dot')
        pywikibot.output(self.to + '.svg')
        self.dot.write_svg(self.to + '.svg')
        pywikibot.output(self.to + '.html')
        header = ('<head><meta charset="UTF-8"/>'
                  '<title>' + self.cat.title(with_ns=False)
                  + '</title> </head>\n'
                  '<div style="position:absolute;">'
                  'Zoom and drag with mouse. '
                  'Nodes are links to Wikipedia.'
                  '</div>\n'
                  '<script '
                  'src="https://unpkg.com/panzoom@9.4.0/dist/panzoom.min.js" '
                  'query="#graph0" name="pz"></script>\n'
                  '<style> svg { height:100%; width:100%; } </style>\n')
        with io.open(self.to + '.html', mode='wb') as o:
            o.write(header.encode())
            o.write(self.dot.create('dot', 'svg'))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(
        description=__doc__,
        epilog='\n'
               'For global options use -help:global '
               'or run pwb.py -help\n\n'
               'Examples:\n'
               './wikigraphviz.py category \n'
               './wikigraphviz.py --style rankdir=BT '
               'category Life \n'
               './wikigraphviz.py --style rankdir=TB '
               ' category Computing\n'
               ' \n',
               formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('action', nargs='?', default=argparse.SUPPRESS,
                    help='only "category" is supported')
    opt = {'action': 'store_true', 'default': argparse.SUPPRESS}
    ap.add_argument('-help:global', help='global pywikibot options', **opt)
    CategoryGraphBot.args(None, ap)
    if config.mylang == 'test':
        config.mylang = 'en'
    local_args = pywikibot.handle_args()
    if config.verbose_output:
        print(config.__dict__)
    args, rest_args = ap.parse_known_args()
    if 'help' in args:
        ap.print_help()
    elif 'help:global' in args:
        pywikibot.show_help(show_global=True)
    elif 'action' in args and args.action == 'category':
        bot = CategoryGraphBot(args)
        bot.run()
    else:
        print("For usage run: wikigraphviz.py --help")
