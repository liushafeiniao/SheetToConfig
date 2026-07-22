# -*- coding: utf-8 -*-
"""
类型定义模板生成器 - 包含完整类型定义和约束说明

【分隔符规则说明】
为了方便使用，系统默认以下分隔符规则：
- 一维列表 (List):  使用 # 分隔，如 1#2#3
- 二维列表 (List2): 使用 | 分隔外层，# 分隔内层，如 1#2|3#4
- 三维列表 (List3): 使用 _ 分隔最外层，| 分隔中层，# 分隔内层，如 1#2|3#4_5#6|7#8

特殊情况可使用 split_list[符号] 自定义分隔符。
"""
import os
import locale as _locale
import tempfile
from openpyxl import Workbook
from openpyxl import load_workbook
from typing import List, Tuple



def _default_locale() -> str:
    """Choose a template language without importing the Qt GUI i18n layer."""
    try:
        name = (_locale.getlocale()[0] or '').replace('_', '-').lower()
    except (ValueError, TypeError):
        name = ''
    if name.startswith(('zh-tw', 'zh-hk', 'zh-hant')):
        return 'zh-TW'
    if name.startswith('zh'):
        return 'zh-CN'
    for locale_id in ('ja', 'ko', 'es', 'en'):
        if name.startswith(locale_id):
            return locale_id
    return 'en'


class TypeDefinitionTemplate:
    """类型定义模板生成器"""
    
    # 完整的类型定义
    DEFAULT_TYPES: List[Tuple[str, str, str]] = [
        # (类型名, 转换函数, 说明)
        ("int", "int", "整数，空值=0"),
        ("float", "float", "浮点数，空值=0.0"),
        ("string", "string", "字符串，空值=''"),
        ("str", "string", "string的别名"),
        ("bool", "bool", "布尔值，空值=false"),
        ("bytes", "bytes", "UTF-8字节串，空值=b''（用于Protobuf）"),
        ("text_key", "text_key", "文本键，数字转int，其他转string"),
        ("qualityEnum", "enum(string,white,green,blue)", "字符串枚举，校验后仍导出原字符串"),
        ("stageEnum", "enum(int,1,2,3)", "整数枚举，校验后仍导出原整数"),

        # === 列表类型（使用默认分隔符）===
        # 一维列表：使用 # 分隔
        ("intList", "split_list(int)", "一维整数列表，使用#分隔，如：1#2#3"),
        ("strList", "split_list(string)", "一维字符串列表，使用#分隔，如：a#b#c"),
        ("floatList", "split_list(float)", "一维浮点列表，使用#分隔，如：1.5#2.5#3.5"),

        # 二维列表：使用 | 分隔外层，# 分隔内层
        ("intList2", "split_list2(int)", "二维整数列表，外层用|分隔，内层用#分隔，如：1#2|3#4|5#6"),
        ("strList2", "split_list2(string)", "二维字符串列表，如：a#b|c#d"),
        ("floatList2", "split_list2(float)", "二维浮点列表，如：1.5#2.5|3.5#4.5"),

        # 三维列表：使用 _ 分隔最外层，| 分隔中层，# 分隔内层
        ("intList3", "split_list3(int)", "三维整数列表，_分隔最外层，|分隔中层，#分隔内层，如：1#2|3#4_5#6|7#8"),
        ("strList3", "split_list3(string)", "三维字符串列表"),
        ("floatList3", "split_list3(float)", "三维浮点列表"),

        # === 自定义分隔符列表（特殊情况使用）===
        ("strList_xhx", "split_list[_](string)", "下划线分隔的字符串列表，如：a_b_c"),
        ("strList_fh", "split_list[;](string)", "分号分隔的字符串列表，如：a;b;c"),

        # === 物品列表类型（使用默认分隔符）===
        ("物品ID", "find_id(item,物品表,id)", "关联物品表的ID"),
        ("物品列表", "split_list(find_id(item,物品表,id))", "物品列表（一维），使用#分隔，如：1001#1002#1003"),
        ("物品列表2", "split_list2(find_id(item,物品表,id))", "物品列表（二维），外层用|分隔，如：1001|1002|1003"),
        ("物品列表3", "split_list3(find_id(item,物品表,id))", "物品列表（三维），_分隔最外层，|分隔中层，#分隔内层"),

        # === 奖励类型 ===
        ("award", "split_list2(split_dict(find_id(item,道具,id) id;int minNum;int maxNum;int chance))",
         "奖励结构，如：1001,1,10,50|1002,2,20,30"),

        # === 路径类型 ===
        ("path", "path(res/,.json)", "路径处理，自动拼接前后缀"),
        ("iconPath", "path(res/icon/,.png)", "图标路径"),
    ]
    
    # 约束方法说明
    CONSTRAINT_DOCS: List[Tuple[str, str, str]] = [
        ("约束方法", "参数", "说明和示例"),
        ("len", "min,max", "长度限制：intList+len(1,5) - 列表长度1-5"),
        ("len2", "min,max", "二维列表元素长度：intList2+len2(1,3) - 每个内层列表长度1-3"),
        ("len3", "min,max", "三维列表元素长度：intList3+len3(1,2)"),
        ("equalLen", "字段名", "长度相同：物品列表2+equalLen(权重) - 与权重字段长度相同"),
        ("equalLen2", "字段名", "二维列表长度相同"),
        ("coexist", "字段名", "同时存在或同时为空：字段A+coexist(字段B)"),
        ("leastOne", "字段名1,字段名2", "至少一个不为空"),
        ("required / notEmpty", "无", "检查原始单元格必填：int+required()"),
        ("range", "min,max", "闭区间数值范围：float+range(0,1)"),
        ("regex", "pattern", "整值正则匹配：string+regex(^item_[0-9]+$)"),
        ("unique", "无", "按转换后的值检查整列唯一：string+unique()"),
    ]

    HEADER_LABELS = {
        'en': ('Name', 'Convert', 'Description'),
        'zh-CN': ('类型名', '转换函数', '说明'),
        'ja': ('名前', '変換関数', '説明'),
        'ko': ('이름', '변환 함수', '설명'),
        'es': ('Nombre', 'Conversión', 'Descripción'),
        'zh-TW': ('型別名稱', '轉換函式', '說明'),
    }

    GUIDE_TEXT = {
        'en': ('TypeDefinition guide', 'List separators', 'Constraints', 'Examples'),
        'zh-CN': ('类型定义说明', '列表分隔符', '约束说明', '示例'),
        'ja': ('型定義ガイド', 'リスト区切り', '制約', '例'),
        'ko': ('타입 정의 안내', '목록 구분자', '제약 조건', '예시'),
        'es': ('Guía de tipos', 'Separadores de listas', 'Restricciones', 'Ejemplos'),
        'zh-TW': ('型別定義說明', '清單分隔符', '約束說明', '範例'),
    }

    GUIDE_COLUMNS = {
        'en': ('Constraint', 'Arguments', 'Description'),
        'zh-CN': ('约束方法', '参数', '说明和示例'),
        'ja': ('制約', '引数', '説明と例'),
        'ko': ('제약 조건', '인수', '설명 및 예시'),
        'es': ('Restricción', 'Argumentos', 'Descripción y ejemplo'),
        'zh-TW': ('約束方法', '參數', '說明與範例'),
    }

    SEPARATOR_ROWS = {
        'en': ('1D: # separates items', '2D: | separates rows, # separates items', '3D: _ separates layers, | rows, # items'),
        'zh-CN': ('一维：# 分隔元素', '二维：| 分隔外层，# 分隔内层', '三维：_ 分隔最外层，| 分隔中层，# 分隔内层'),
        'ja': ('1次元：# で要素を区切る', '2次元：| が行、# が要素を区切る', '3次元：_ が層、| が行、# が要素を区切る'),
        'ko': ('1차원: #로 요소 구분', '2차원: |는 행, #는 요소 구분', '3차원: _는 층, |는 행, #는 요소 구분'),
        'es': ('1D: # separa elementos', '2D: | separa filas y # elementos', '3D: _ separa capas, | filas y # elementos'),
        'zh-TW': ('一維：# 分隔元素', '二維：| 分隔外層，# 分隔內層', '三維：_ 分隔最外層，| 分隔中層，# 分隔內層'),
    }

    _LOCALIZED_GROUPS = {
        'en': {
            'int': 'Integer; empty values become 0', 'float': 'Float; empty values become 0.0',
            'string': 'String; empty values become an empty string', 'str': 'Alias of string',
            'bool': 'Boolean; empty values become false', 'bytes': 'UTF-8 bytes for Protobuf',
            'text_key': 'Text key: numeric values become int, others string',
            'enum': 'Enum values are validated and exported unchanged', 'list': 'List using the configured separator',
            'path': 'Path with the configured prefix and suffix', 'ref': 'Reference ID from another workbook',
            'dict': 'Structured dictionary value',
        },
        'zh-CN': {
            'int': '整数，空值=0', 'float': '浮点数，空值=0.0', 'string': '字符串，空值为空字符串',
            'str': 'string 的别名', 'bool': '布尔值，空值=false', 'bytes': 'UTF-8 字节串（用于 Protobuf）',
            'text_key': '文本键：数字转整数，其他转字符串', 'enum': '枚举值校验后原样导出',
            'list': '按配置分隔符解析列表', 'path': '按前后缀处理路径', 'ref': '引用其他工作簿的 ID',
            'dict': '结构化字典值',
        },
        'ja': {
            'int': '整数、空値は0', 'float': '浮動小数、空値は0.0', 'string': '文字列、空値は空文字列',
            'str': 'string の別名', 'bool': '真偽値、空値はfalse', 'bytes': 'Protobuf 用 UTF-8 バイト列',
            'text_key': 'テキストキー：数値は整数、それ以外は文字列', 'enum': '列挙値を検証してそのまま出力',
            'list': '指定した区切りでリストを解析', 'path': '前後の接頭辞・接尾辞でパスを処理',
            'ref': '別のワークブックの ID を参照', 'dict': '構造化された辞書値',
        },
        'ko': {
            'int': '정수, 빈 값은 0', 'float': '실수, 빈 값은 0.0', 'string': '문자열, 빈 값은 빈 문자열',
            'str': 'string의 별칭', 'bool': '불리언, 빈 값은 false', 'bytes': 'Protobuf용 UTF-8 바이트',
            'text_key': '텍스트 키: 숫자는 정수, 그 외는 문자열', 'enum': '열거형 값을 검증하고 그대로 출력',
            'list': '설정된 구분자로 목록을 변환', 'path': '지정한 접두사와 접미사로 경로 처리',
            'ref': '다른 워크북의 ID 참조', 'dict': '구조화된 딕셔너리 값',
        },
        'es': {
            'int': 'Entero; los valores vacíos son 0', 'float': 'Decimal; los valores vacíos son 0.0',
            'string': 'Cadena; los valores vacíos son cadena vacía', 'str': 'Alias de string',
            'bool': 'Booleano; los valores vacíos son false', 'bytes': 'Bytes UTF-8 para Protobuf',
            'text_key': 'Clave de texto: números a entero, otros a cadena', 'enum': 'Enum validado y exportado sin cambios',
            'list': 'Lista separada según el delimitador configurado', 'path': 'Ruta con prefijo y sufijo configurados',
            'ref': 'ID de referencia de otro libro', 'dict': 'Valor de diccionario estructurado',
        },
        'zh-TW': {
            'int': '整數，空值=0', 'float': '浮點數，空值=0.0', 'string': '字串，空值為空字串',
            'str': 'string 的別名', 'bool': '布林值，空值=false', 'bytes': 'Protobuf 使用的 UTF-8 位元組',
            'text_key': '文字鍵：數字轉整數，其餘轉字串', 'enum': '列舉值驗證後原樣輸出',
            'list': '依設定分隔符解析清單', 'path': '依前後綴處理路徑', 'ref': '引用其他活頁簿的 ID',
            'dict': '結構化字典值',
        },
    }

    @classmethod
    def _localized_description(cls, type_name: str, default: str, locale_id: str) -> str:
        """Return a localized explanation while keeping the machine expression stable."""
        groups = cls._LOCALIZED_GROUPS.get(locale_id, cls._LOCALIZED_GROUPS['en'])
        if type_name in groups:
            return groups[type_name]
        if type_name in {'qualityEnum', 'stageEnum'}:
            return groups['enum']
        if type_name in {'物品ID', '物品列表', '物品列表2', '物品列表3', 'itemId'}:
            return groups['ref'] if type_name == '物品ID' else groups['list']
        if type_name == 'award':
            return groups['dict']
        if type_name == 'iconPath' or type_name == 'path':
            return groups['path']
        if type_name.startswith(('intList', 'strList', 'floatList')):
            return groups['list']
        return default if locale_id == 'zh-CN' else groups['string']

    @classmethod
    def _localized_constraint_rows(cls, locale_id: str):
        if locale_id == 'zh-CN':
            return cls.CONSTRAINT_DOCS[1:]
        descriptions = {
            'en': {
                'len': 'List length range', 'len2': 'Inner list length range', 'len3': 'Nested list length range',
                'equalLen': 'Same outer length as another field', 'equalLen2': 'Same two-dimensional length',
                'coexist': 'Both fields exist or are both empty', 'leastOne': 'At least one field is present',
                'required / notEmpty': 'Original cell is required', 'range': 'Closed numeric range',
                'regex': 'Full-value regular expression', 'unique': 'Converted values must be unique',
            },
            'ja': {
                'len': 'リスト長の範囲', 'len2': '内側リスト長の範囲', 'len3': '入れ子リスト長の範囲',
                'equalLen': '他フィールドと外側の長さを一致', 'equalLen2': '2次元の長さを一致',
                'coexist': '両方存在または両方空', 'leastOne': '少なくとも1つを入力',
                'required / notEmpty': '元セルを必須にする', 'range': '数値の閉区間',
                'regex': '値全体の正規表現', 'unique': '変換後の値を一意にする',
            },
            'ko': {
                'len': '목록 길이 범위', 'len2': '내부 목록 길이 범위', 'len3': '중첩 목록 길이 범위',
                'equalLen': '다른 필드와 외부 길이 일치', 'equalLen2': '2차원 길이 일치',
                'coexist': '두 필드가 함께 존재하거나 비어 있음', 'leastOne': '하나 이상 입력',
                'required / notEmpty': '원본 셀 필수', 'range': '닫힌 숫자 범위',
                'regex': '전체 값 정규식', 'unique': '변환된 값의 유일성',
            },
            'es': {
                'len': 'Rango de longitud de lista', 'len2': 'Rango de longitud interna', 'len3': 'Rango de lista anidada',
                'equalLen': 'Misma longitud externa que otro campo', 'equalLen2': 'Misma longitud bidimensional',
                'coexist': 'Ambos campos presentes o vacíos', 'leastOne': 'Al menos un campo presente',
                'required / notEmpty': 'Celda original obligatoria', 'range': 'Rango numérico cerrado',
                'regex': 'Expresión regular del valor completo', 'unique': 'Valores convertidos únicos',
            },
            'zh-TW': {
                'len': '清單長度範圍', 'len2': '內層清單長度範圍', 'len3': '巢狀清單長度範圍',
                'equalLen': '與其他欄位外層長度相同', 'equalLen2': '二維長度相同',
                'coexist': '兩欄同時存在或同時為空', 'leastOne': '至少填寫一欄',
                'required / notEmpty': '原始儲存格必填', 'range': '閉區間數值範圍',
                'regex': '完整值正規表示式', 'unique': '轉換後的值必須唯一',
            },
        }.get(locale_id, {})
        return [
            (name, args, descriptions.get(name, description))
            for name, args, description in cls.CONSTRAINT_DOCS[1:]
        ]
    
    @classmethod
    def _write_atomic(cls, workbook, target_path: str) -> None:
        parent = os.path.dirname(os.path.abspath(target_path))
        fd, temp_path = tempfile.mkstemp(prefix='.typedefinition-', suffix='.xlsx', dir=parent)
        os.close(fd)
        try:
            workbook.save(temp_path)
            # Close before replace; Windows keeps workbook handles locked.
            workbook.close()
            os.replace(temp_path, target_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @classmethod
    def _guide_sheet(cls, workbook, locale_id: str):
        labels = cls.GUIDE_TEXT.get(locale_id, cls.GUIDE_TEXT['en'])
        if 'Guide' in workbook.sheetnames:
            return False
        ws = workbook.create_sheet('Guide')
        ws.append([labels[0]])
        ws.append([])
        ws.append([labels[1]])
        ws.append(list(cls.SEPARATOR_ROWS.get(locale_id, cls.SEPARATOR_ROWS['en'])))
        ws.append([])
        ws.append(list(cls.GUIDE_COLUMNS.get(locale_id, cls.GUIDE_COLUMNS['en'])))
        for row in cls._localized_constraint_rows(locale_id):
            ws.append(row)
        ws.append([])
        ws.append([labels[3]])
        examples = {
            'en': ('Cross-workbook reference', 'Alias for find_id'),
            'zh-CN': ('跨工作簿引用', 'find_id 的同义简写'),
            'ja': ('ワークブック間参照', 'find_id の短縮形'),
            'ko': ('워크북 간 참조', 'find_id의 별칭'),
            'es': ('Referencia entre libros', 'Alias de find_id'),
            'zh-TW': ('跨活頁簿引用', 'find_id 的同義簡寫'),
        }.get(locale_id, ('Cross-workbook reference', 'Alias for find_id'))
        ws.append(['find_id(item, Item, id)', examples[0]])
        ws.append(['find(item, Item, id)', examples[1]])
        return True

    @classmethod
    def create_template(cls, table_dir: str, locale: str = None):
        """Create or non-destructively extend a TypeDefinition workbook."""
        type_def_path = os.path.join(table_dir, "TypeDefinition.xlsx")

        os.makedirs(table_dir, exist_ok=True)
        locale_id = locale or _default_locale()
        if locale_id not in cls.HEADER_LABELS:
            locale_id = 'en'

        if os.path.exists(type_def_path):
            workbook = load_workbook(type_def_path)
            changed = False
            if 'CODE' not in workbook.sheetnames:
                workbook.close()
                raise ValueError('TypeDefinition.xlsx is missing the CODE worksheet')
            ws = workbook['CODE']
            existing = {
                str(row[0].value).strip().casefold()
                for row in ws.iter_rows(min_row=2)
                if row and row[0].value
            }
            for type_name, convert_func, desc in cls.DEFAULT_TYPES:
                if type_name.casefold() not in existing:
                    ws.append([type_name, convert_func, cls._localized_description(type_name, desc, locale_id)])
                    existing.add(type_name.casefold())
                    changed = True
            changed = cls._guide_sheet(workbook, locale_id) or changed
            if changed:
                try:
                    cls._write_atomic(workbook, type_def_path)
                finally:
                    workbook.close()
            else:
                workbook.close()
            return

        workbook = Workbook()
        ws = workbook.active
        ws.title = "CODE"
        ws.append(list(cls.HEADER_LABELS[locale_id]))
        for type_name, convert_func, desc in cls.DEFAULT_TYPES:
            ws.append([type_name, convert_func, cls._localized_description(type_name, desc, locale_id)])
        cls._guide_sheet(workbook, locale_id)
        cls._write_atomic(workbook, type_def_path)
    
    @classmethod
    def ensure_exists(cls, table_dir: str, locale: str = None):
        """Create a missing workbook without modifying an existing one."""
        type_def_path = os.path.join(table_dir, "TypeDefinition.xlsx")
        if os.path.exists(type_def_path):
            workbook = load_workbook(type_def_path, read_only=True, data_only=True)
            try:
                if 'CODE' not in workbook.sheetnames:
                    raise ValueError('TypeDefinition.xlsx is missing the CODE worksheet')
            finally:
                workbook.close()
            return
        cls.create_template(table_dir, locale=locale)
