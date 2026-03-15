import pickle
import sys

from annotated_doc import Doc

if sys.version_info >= (3, 9):
    from typing import Annotated, get_type_hints
else:
    from typing_extensions import Annotated, get_type_hints


def test_doc_basic() -> None:
    doc = Doc("This is a test documentation.")
    assert doc.documentation == "This is a test documentation."
    assert repr(doc) == "Doc('This is a test documentation.')"
    assert hash(doc) == hash("This is a test documentation.")
    assert doc == Doc("This is a test documentation.")
    assert doc != Doc("Different documentation.")
    assert doc != "Not a Doc instance"


def test_annotation():
    def hi(name: Annotated[str, Doc("Who to say hi to")]) -> None:  # pragma: no cover
        pass

    hints = get_type_hints(hi, include_extras=True)
    doc_info: Doc = hints["name"].__metadata__[0]
    assert doc_info.documentation == "Who to say hi to"
    assert isinstance(doc_info, Doc)


def test_repr():
    doc_info = Doc("Who to say hi to")
    assert repr(doc_info) == "Doc('Who to say hi to')"


def test_hashability():
    doc_info = Doc("Who to say hi to")
    assert isinstance(hash(doc_info), int)
    assert hash(doc_info) != hash(Doc("Who not to say hi to"))


def test_equality():
    doc_info = Doc("Who to say hi to")
    # Equal to itself
    assert doc_info == doc_info
    # Equal to another instance with the same string
    assert doc_info == Doc("Who to say hi to")
    # Not equal to another instance with a different string
    assert doc_info != Doc("Who not to say hi to")


def test_pickle():
    doc_info = Doc("Who to say hi to")
    for proto in range(pickle.HIGHEST_PROTOCOL + 1):
        pickled = pickle.dumps(doc_info, protocol=proto)
        assert doc_info == pickle.loads(pickled)
