import os
import logging
import typing
from tree_sitter import Language, Parser, Node, Query, QueryCursor
import tree_sitter_python
import tree_sitter_cpp
import json

logging.basicConfig(level=logging.DEBUG)

def list_dataset_files(dataset: str, suffix: str) -> list[str]:
    if not os.path.exists(dataset):
        raise FileNotFoundError(f"The dataset path '{dataset}' does not exist.")
    logging.info(f"列出 {dataset} 的 {suffix} 文件")
    return [f for f in os.listdir(dataset) if os.path.isfile(os.path.join(dataset, f)) and f.endswith(suffix)]

def extract_base_filenames(file_list: list[str]) -> set[str]:
    return {os.path.splitext(f)[0] for f in file_list}

def read_file(file_path: str) -> str:
    logging.info(f"讀取 {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def query(content: str, language: Language, query_string: str) -> dict[str, list[str]]:
    logging.info("解析文件內容")
    parser = Parser(language)
    tree = parser.parse(bytes(content, "utf8"))
    
    logging.info("開始查詢")
    captured = QueryCursor(Query(language, query_string)).captures(tree.root_node)
    logging.info("查詢完成")
    
    for key in captured.keys():
        captured[key] = list(map(lambda node: str(node.text, "utf-8"), captured[key]))
        
    return captured

def assert_have_keys(arg: dict, expected: list[str]):
    keys = arg.keys()
    for ex in expected:
        if not ex in keys:
            raise ValueError(f"{ex} not in {keys}")

class Sample(typing.TypedDict):
    cpp: str
    python: str
    test_statements: list[str]

if __name__ == '__main__':
    ROOT_DIR = os.path.join("data", "evaluation", "geeks_for_geeks_successful_test_scripts")
    CPP_ROOT_DIR = os.path.join(ROOT_DIR, "cpp")
    PYTHON_ROOT_DIR = os.path.join(ROOT_DIR, "python")
    F_GOLD = "f_gold"
    
    # 整理相同名稱的 python 和 cpp 檔案
    cpp_list_names = extract_base_filenames(list_dataset_files(CPP_ROOT_DIR, "cpp"))
    python_list_names = extract_base_filenames(list_dataset_files(PYTHON_ROOT_DIR, "py"))
    
    names = [name for name in cpp_list_names if name in python_list_names]

    samples: dict[str, Sample] = {name: {"cpp": "", "python": "", "test_statements": []} for name in names}
    
    # 在 cpp 檔案中擷取函式內容
    CPP_LANGUAGE = Language(tree_sitter_cpp.language())
    CPP_QUERY = f"""
        (preproc_include) @include
        (using_declaration) @using
        (function_definition
            declarator: (function_declarator
                declarator: (identifier) @func_name
                (#eq? @func_name "{F_GOLD}")
            )
        ) @func
    """
    
    for name in names:
        file_content = read_file(os.path.join(CPP_ROOT_DIR, f"{name}.cpp"))
        cpp_queried = query(file_content, CPP_LANGUAGE, CPP_QUERY)
        
        assert_have_keys(cpp_queried, ["include", "using", "func_name", "func"])
        assert cpp_queried["func_name"][0] == F_GOLD
        
        include = "".join(cpp_queried["include"])
        using = cpp_queried["using"][0]
        func = cpp_queried["func"][0].replace(F_GOLD, name.lower())
        samples[name]["cpp"] = "\n".join([include, using, func])
    
    # 在 python 檔案中擷取函式內容和測試的輸入值
    PYTHON_LANGUAGE = Language(tree_sitter_python.language())
    PARAM = "param"
    PYTHON_QUERY = f"""
        (import_statement) @import
        (import_from_statement) @from
        (function_definition
            name: (
                (identifier) @func_name
                (#eq? @func_name "{F_GOLD}")
            )
        ) @func
        (assignment
            left: (identifier) @var_name
            (#eq? @var_name "{PARAM}")
            right: (list) @var_value
        )
    """
    
    for name in names:
        file_content = read_file(os.path.join(PYTHON_ROOT_DIR, f"{name}.py"))
        python_queried = query(file_content, PYTHON_LANGUAGE, PYTHON_QUERY)
        
        assert_have_keys(python_queried, ["func_name", "func", "var_name", "var_value"])
        assert python_queried["func_name"][0] == F_GOLD
        assert python_queried["var_name"][0] == PARAM
        
        func_name = name.lower()
        imports = "".join(python_queried["import"]) if "import" in python_queried.keys() else ""
        froms = "".join(python_queried["from"]) if "from" in python_queried.keys() else ""
        func = python_queried["func"][0].replace(F_GOLD, func_name)
        samples[name]["python"] = "\n".join([imports, froms, func])
        
        for param in eval(python_queried["var_value"][0]):
            exec(samples[name]["python"])
            func_call = f"{func_name}{param}"
            logging.info(f"呼叫 {func_call}")
            
            err = None
            try:
                expect = eval(func_call)
            except Exception as e:
                err = e
        
            if not err:
                test_left = f"assert {func_call}"
                test_right = f"'{expect}'" if type(expect) == str else expect
                statement = f"{test_left} == {test_right}"
            else:
                statement = f"try:\n\t{func_call}except Exception as err:\n\tassert err == {str(err)}"
            
            samples[name]["test_statements"].append(statement)
            logging.debug(f"成功產生 {name} : {param} 測試")
        logging.info(f"成功取得全部測試句子")
        
    # 將 cpp 函式、python 函式和測試句子整合到 samples.json 中
    with open("samples.json", "w") as sample_file:
        json.dump(samples, sample_file)