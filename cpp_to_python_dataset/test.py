from typing import Generator
from tree_sitter import Language, Parser, Tree, Node, QueryCursor, Query
import tree_sitter_python
import tree_sitter_cpp

PY_LANGUAGE = Language(tree_sitter_python.language())
# CPP_LANGUAGE = Language(tree_sitter_cpp.language())
parser = Parser()
parser.language = PY_LANGUAGE

with open("data\\evaluation\\geeks_for_geeks_successful_test_scripts\python\\PROGRAM_TO_FIND_THE_AREA_OF_PENTAGON.py", "r", encoding="utf-8") as f:
    content = f.read()
    
tree = parser.parse(bytes(content, "utf8"))

# def traverse_tree(tree: Tree) -> Generator[Node, None, None]:
#     cursor = tree.walk()

#     visited_children = False
#     while True:
#         if not visited_children:
#             yield cursor.node
#             if not cursor.goto_first_child():
#                 visited_children = True
#         elif cursor.goto_next_sibling():
#             visited_children = False
#         elif not cursor.goto_parent():
#             break

# node_infos = map(lambda node: (node.type, str(node.text, "utf-8")), traverse_tree(tree))
    
# for info in node_infos:
#     print(info)

query = """
(import_statement) @import
(import_from_statement) @from
(function_definition
    name: (
        (identifier) @func_name
        (#eq? @func_name "f_gold")
    )
) @func
(assignment
    left: (identifier) @var
    (#eq? @var "param")
    right: (list) @value
)
"""
captured = QueryCursor(Query(PY_LANGUAGE, query)).captures(tree.root_node)
for key, nodes in captured.items():
    for node in nodes:
        print(f"{key}: {node.type} {str(node.text, 'utf-8')}")