"""
Unit tests for edx_argoutils/record.py"""
import pytest
from datetime import datetime, date
import pytz
from collections import OrderedDict

from edx_argoutils.record import (
    Record,
    Field,
    SparseRecord,
    StringField,
    IntegerField,
    BooleanField,
    DateTimeField,
    FloatField,
    DateField,
    DelimitedStringField,
    RecordMapper,
    HiveTsvEncoder,
    DEFAULT_NULL_VALUE
)

@pytest.fixture
def simple_record_class():
    class SimpleRecord(Record):
        name = StringField(length=50)
        age = IntegerField()
        active = BooleanField()
    return SimpleRecord

@pytest.fixture
def complex_record_class():
    class ComplexRecord(Record):
        timestamp = DateTimeField()
        count = IntegerField(nullable=False)
        description = StringField(length=100, nullable=True)
    return ComplexRecord

class TestRecord:
    def test_basic_initialization(self, simple_record_class):
        record = simple_record_class(name="John Doe", age=30, active=True)
        assert record.name == "John Doe"
        assert record.age == 30
        assert record.active is True

    def test_positional_arguments(self, simple_record_class):
        record = simple_record_class("Jane Doe", 25, False)
        assert record.name == "Jane Doe"
        assert record.age == 25
        assert record.active is False

    def test_missing_required_fields(self, complex_record_class):
        with pytest.raises(TypeError):
            complex_record_class(timestamp=datetime.now(pytz.UTC))

    def test_null_validation(self, complex_record_class):
        with pytest.raises(ValueError):
            complex_record_class(count=None, timestamp=datetime.now(pytz.UTC))

    def test_immutability(self, simple_record_class):
        record = simple_record_class(name="John Doe", age=30, active=True)
        with pytest.raises(TypeError):
            record.name = "Jane Doe"

    def test_equality(self, simple_record_class):
        record1 = simple_record_class(name="John Doe", age=30, active=True)
        record2 = simple_record_class(name="John Doe", age=30, active=True)
        record3 = simple_record_class(name="Jane Doe", age=30, active=True)
        
        assert record1 == record2
        assert record1 != record3
        assert hash(record1) == hash(record2)

    def test_to_string_tuple(self, simple_record_class):
        record = simple_record_class(name="John Doe", age=30, active=True)
        string_tuple = record.to_string_tuple()
        assert len(string_tuple) == 3
        assert string_tuple[0] == b"John Doe"
        assert string_tuple[1] == b"30"
        assert string_tuple[2] == b"1"

    def test_to_ordered_dict(self, simple_record_class):
        record = simple_record_class(name="John Doe", age=30, active=True)
        ordered_dict = record.to_ordered_dict()
        assert isinstance(ordered_dict, OrderedDict)
        assert ordered_dict['name'] == "John Doe"
        assert ordered_dict['age'] == 30
        assert ordered_dict['active'] is True
    
    def test_invalid_field_value(self, simple_record_class):
        with pytest.raises(ValueError):
            simple_record_class(name=123, age="not an int", active="not a bool")

    def test_extra_kwargs(self, simple_record_class):
        with pytest.raises(TypeError):
            simple_record_class(name="John", age=30, active=True, extra_field="invalid")

    def test_replace(self, simple_record_class):
        record = simple_record_class(name="John", age=30, active=True)
        new_record = record.replace(name="Jane")
        assert new_record.name == "Jane"
        assert new_record.age == record.age
        assert new_record.active == record.active
        
    def test_get_sql_schema(self, simple_record_class):
        schema = simple_record_class.get_sql_schema()
        assert isinstance(schema, list)
        assert len(schema) == 3
        assert schema[0][0] == 'name'
        assert 'VARCHAR' in schema[0][1]

    def test_get_hive_schema(self, simple_record_class):
        schema = simple_record_class.get_hive_schema()
        assert isinstance(schema, list)
        assert len(schema) == 3
        
    def test_get_elasticsearch_properties(self, simple_record_class):
        properties = simple_record_class.get_elasticsearch_properties()
        assert isinstance(properties, dict)
        assert 'name' in properties
        assert properties['name']['type'] == 'string'

    def test_get_restructured_text(self, simple_record_class):
        doc = simple_record_class.get_restructured_text()
        assert isinstance(doc, str)
        assert 'StringField' in doc
        assert 'IntegerField' in doc
        assert 'BooleanField' in doc

    def test_from_string_tuple(self, simple_record_class):
        string_tuple = (b"John Doe", b"30", b"1")
        record = simple_record_class.from_string_tuple(string_tuple)
        assert record.name == "John Doe"
        assert record.age == 30
        assert record.active is True

    def test_from_tsv(self, simple_record_class):
        tsv_str = "John Doe\t30\t1"
        record = simple_record_class.from_tsv(tsv_str)
        assert record.name == "John Doe"
        assert record.age == 30
        assert record.active is True

class TestSparseRecord:
    @pytest.fixture
    def sparse_record_class(self):
        class TestSparseRecord(SparseRecord):
            name = StringField()
            age = IntegerField()
            email = StringField(nullable=True)
        return TestSparseRecord

    def test_sparse_initialization(self, sparse_record_class):
        record = sparse_record_class(name="John Doe")
        assert record.name == "John Doe"
        assert record.age is None
        assert record.email is None

class TestFields:
    def test_string_field_validation(self):
        field = StringField(length=10)
        assert field.validate("test") == []
        assert field.validate("") == []
        assert len(field.validate("x" * 11)) == 1  # Too long

    def test_string_field_truncation(self):
        field = StringField(length=5, truncate=True)
        assert field.serialize_to_string("123456") == "12345"

    def test_integer_field(self):
        field = IntegerField()
        assert field.validate(42) == []
        assert len(field.validate("42")) > 0
        assert field.deserialize_from_string("42") == 42

    def test_boolean_field(self):
        field = BooleanField()
        assert field.validate(True) == []
        assert field.validate(False) == []
        assert len(field.validate(1)) > 0
        assert field.serialize_to_string(True) == "1"
        assert field.deserialize_from_string("1") is True

    def test_float_field(self):
        field = FloatField()
        assert field.validate(3.14) == []
        # Test valid integer
        assert field.validate(42) == []  # Integers should be valid for float fields
        # Test valid string that can be converted to float
        assert field.validate("3.14") == []
        # Test string that cannot be converted to float
        assert len(field.validate("not a float")) > 0
        # Test deserialization
        assert field.deserialize_from_string("3.14") == pytest.approx(3.14)
        assert len(field.validate({"foo": "bar"})) > 0

    def test_date_field(self):
        field = DateField()
        test_date = date(2023, 1, 1)
        assert field.validate(test_date) == []
        assert len(field.validate("2023-01-01")) > 0
        assert field.deserialize_from_string("2023-01-01") == test_date

    def test_delimited_string_field(self):
        field = DelimitedStringField()
        test_value = ("a", "b", "c")
        assert field.validate(test_value) == []
        serialized = field.serialize_to_string(test_value)
        assert field.deserialize_from_string(serialized) == test_value
    def test_field_counter_increment(self):
        initial_counter = Field.counter
        StringField()
        assert Field.counter == initial_counter + 1

    def test_string_field_encoding(self):
        field = StringField()
        assert field.serialize_to_string("test") == "test"
        assert field.serialize_to_string(u"test") == u"test"
        assert field.serialize_to_string(b"test") == "test"

    def test_delimited_string_field_custom_delimiter(self):
        field = DelimitedStringField()
        field.delimiter = '|'
        test_value = ("a", "b", "c")
        serialized = field.serialize_to_string(test_value)
        assert serialized == "a|b|c"
        assert field.deserialize_from_string(serialized) == test_value

class TestDateTimeField:
    @pytest.fixture
    def datetime_field(self):
        return DateTimeField()

    def test_datetime_validation(self, datetime_field):
        now = datetime.now(pytz.UTC)
        assert datetime_field.validate(now) == []
        assert len(datetime_field.validate(datetime.now())) > 0  # Naive datetime
        assert len(datetime_field.validate(datetime(1899, 1, 1, tzinfo=pytz.UTC))) > 0  # Pre-1900

    def test_datetime_serialization(self, datetime_field):
        now = datetime.now(pytz.UTC)
        serialized = datetime_field.serialize_to_string(now)
        deserialized = datetime_field.deserialize_from_string(serialized)
        assert deserialized.replace(microsecond=0) == now.replace(microsecond=0)

    def test_invalid_datetime_string(self, datetime_field):
        assert datetime_field.deserialize_from_string(None) is None
        assert datetime_field.deserialize_from_string("invalid") is None

class TestRecordMapper:
    @pytest.fixture
    def test_record_class(self):
        class TestRecord(Record):
            name = StringField(length=50)
            age = IntegerField()
            registered = DateTimeField()
        return TestRecord

    @pytest.fixture
    def test_mapper(self, test_record_class):
        class TestMapper(RecordMapper):
            @property
            def record_class(self):
                return test_record_class

            def add_record_field_mapping(self, field_key, add_event_mapping_entry):
                mapping = {
                    'name': 'root.user.name',
                    'age': 'root.user.age',
                    'registered': 'root.user.registered_at'
                }
                if field_key in mapping:
                    add_event_mapping_entry(mapping[field_key])
        return TestMapper()

    def test_mapping(self, test_mapper, test_record_class):
        input_dict = {
            'user': {
                'name': 'John Doe',
                'age': '30',
                'registered_at': '2023-01-01T00:00:00Z'
            }
        }
        
        record_dict = {}
        test_mapper.add_info(record_dict, input_dict)
        
        record = test_record_class(**record_dict)
        assert record.name == 'John Doe'
        assert record.age == 30
        assert isinstance(record.registered, datetime)

    def test_calculated_entry(self, test_mapper):
        record_dict = {}
        test_mapper.add_calculated_entry(record_dict, 'name', 'John Doe')
        assert record_dict['name'] == 'John Doe'
    
    def test_nested_mapping(self, test_mapper):
        input_dict = {
            'user': {
                'profile': {
                    'name': 'John Doe',
                    'age': '30'
                },
                'registered_at': '2023-01-01T00:00:00Z'
            }
        }
        record_dict = {}
        test_mapper.add_info(record_dict, input_dict)
        assert 'name' not in record_dict  # Should not map nested field without proper mapping

    def test_list_handling(self, test_mapper):
        input_dict = {
            'user': {
                'name': ['John', 'Doe'],
                'age': '30',
                'registered_at': '2023-01-01T00:00:00Z'
            }
        }
        record_dict = {}
        test_mapper.add_info(record_dict, input_dict)
        assert 'name' not in record_dict  # Should not map list values

    def test_null_input(self, test_mapper):
        record_dict = {}
        test_mapper.add_info(record_dict, None)
        assert len(record_dict) == 0

class TestHiveTsvEncoder:
    @pytest.fixture
    def encoder(self):
        return HiveTsvEncoder()

    def test_encode_null(self, encoder):
        assert encoder.encode(None, StringField()) == DEFAULT_NULL_VALUE

    def test_encode_string(self, encoder):
        assert encoder.encode("test", StringField()) == b"test"

    def test_decode_null(self, encoder):
        assert encoder.decode(DEFAULT_NULL_VALUE, StringField()) is None

    def test_decode_string(self, encoder):
        assert encoder.decode(b"test", StringField()) == "test"

    def test_normalize_whitespace(self):
        encoder = HiveTsvEncoder(normalize_whitespace=True)
        assert encoder.encode("test  test", StringField()) == b"test test"
    
    def test_normalize_whitespace_field_level(self, encoder):
        field = StringField(normalize_whitespace=True)
        assert encoder.encode("test  test", field) == b"test test"

    def test_unicode_handling(self, encoder):
        unicode_text = u"测试"
        encoded = encoder.encode(unicode_text, StringField())
        assert isinstance(encoded, bytes)
        assert encoder.decode(encoded, StringField()) == unicode_text

    def test_mixed_content(self, encoder):
        mixed_text = "test\t test\n test"
        encoded = encoder.encode(mixed_text, StringField())
        assert encoder.decode(encoded, StringField()) == mixed_text