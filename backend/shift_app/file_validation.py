"""Validate invoice PDFs without executing actions or extracting stream data."""
import io
from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject
from .finance import RuleError


def validate_pdf(blob):
    try:
        reader = PdfReader(io.BytesIO(blob), strict=True)
        if sum(len(entries) for entries in reader.xref.values()) + len(reader.xref_objStm) > 10000:
            raise ValueError('too many objects')
        if reader.is_encrypted:
            raise ValueError('encrypted')
        if not 1 <= len(reader.pages) <= 200:
            raise ValueError('pages')
        seen = set()
        visited = 0
        active_keys = {'/JS', '/JavaScript', '/Launch', '/EmbeddedFiles', '/RichMedia', '/XFA', '/OpenAction', '/AA'}

        def visit(obj, depth=0):
            nonlocal visited
            visited += 1
            if visited > 10000 or depth > 30:
                raise ValueError('complex')
            if isinstance(obj, IndirectObject):
                key = (obj.idnum, obj.generation)
                if key in seen:
                    return
                seen.add(key)
                return visit(obj.get_object(), depth + 1)
            if isinstance(obj, DictionaryObject):
                if active_keys.intersection(str(key) for key in obj):
                    raise ValueError('active content')
                for value in obj.values():
                    visit(value, depth + 1)
            elif isinstance(obj, ArrayObject):
                for value in obj:
                    visit(value, depth + 1)

        visit(reader.root_object)
    except Exception:
        raise RuleError('أرفق PDF صالحًا، غير مشفر ولا يتضمن سكربتات أو ملفات مدمجة، وبحد أقصى 200 صفحة.') from None
