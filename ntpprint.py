from io import StringIO
import pprint


# https://stackoverflow.com/questions/30062384/pretty-print-namedtuple
class MyPrettyPrinter(pprint.PrettyPrinter):
    def format_namedtuple(self, object, stream, indent, allowance, context, level):
        # Code almost equal to _format_dict, see pprint code
        write = stream.write
        write(object.__class__.__name__ + '(')
        object_dict = object._asdict()
        length = len(object_dict)
        if length:
            # We first try to print inline, and if it is too large then we print it on multiple lines
            inline_stream = StringIO()
            self.format_namedtuple_items(object_dict.items(), inline_stream, indent, allowance + 1,
                                         context, level, inline=True)
            max_width = self._width - indent - allowance
            if len(inline_stream.getvalue()) > max_width:
                self.format_namedtuple_items(object_dict.items(), stream, indent, allowance + 1,
                                             context, level, inline=False)
            else:
                stream.write(inline_stream.getvalue())

    def format_namedtuple_items(self, items, stream, indent, allowance, context, level,
                                inline=False):
        # Code almost equal to _format_dict_items, see pprint code
        indent += self._indent_per_level
        write = stream.write
        last_index = len(items) - 1
        if inline:
            delimnl = ', '
        else:
            delimnl = ',\n' + ' ' * indent
            write('\n' + ' ' * indent)
        for i, (key, ent) in enumerate(items):
            last = i == last_index
            write(key + '=')
            self._format(ent, stream, indent + len(key) + 1,
                         allowance if last else 1,
                         context, level)
            if not last:
                write(delimnl)

    def _format(self, object, stream, indent, allowance, context, level):
        # We dynamically add the types of our namedtuple and namedtuple like
        # classes to the _dispatch object of pprint that maps classes to
        # formatting methods
        # We use a simple criteria (_asdict method) that allows us to use the
        # same formatting on other classes but a more precise one is possible
        if hasattr(object, '_asdict') and type(object).__repr__ not in self._dispatch:
            self._dispatch[type(object).__repr__] = MyPrettyPrinter.format_namedtuple
        super()._format(object, stream, indent, allowance, context, level)


pprint = MyPrettyPrinter(indent=2).pprint


def nt_asdict(obj):
    if hasattr(obj, '_asdict'):
        obj = {'__name__': type(obj).__name__, **obj._asdict()}

    if hasattr(obj, 'items'):
        obj = {k: nt_asdict(v) for k, v in obj.items()}
    elif not isinstance(obj, (str, bytes)):
        try:
            it = iter(obj)
        except TypeError:
            it = None

        if it is not None:
            obj = [nt_asdict(v) for v in it]

    return obj
