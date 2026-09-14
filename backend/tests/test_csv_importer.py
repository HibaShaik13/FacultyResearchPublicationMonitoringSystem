import os
import pytest
from app.seed.csv_importer import FacultyCSVParser

def test_name_normalization():
    parser = FacultyCSVParser("dummy.csv")
    
    # Test ALL CAPS with Dr prefix
    prefix, norm, fname, lname, clean = parser._normalize_name("Dr MD OQAIL AHMAD")
    assert prefix == "Dr"
    assert norm == "Md Oqail Ahmad"
    assert fname == "Md"
    assert lname == "Oqail Ahmad"
    assert clean == "Dr MD OQAIL AHMAD"

    # Test title casing and dots
    prefix, norm, fname, lname, clean = parser._normalize_name("Mr .Kiran Kumar Kaveti")
    assert prefix == "Mr"
    assert norm == "Kiran Kumar Kaveti"
    assert fname == "Kiran"
    assert lname == "Kumar Kaveti"

    # Test trailing dot
    prefix, norm, fname, lname, clean = parser._normalize_name("Dr Vijitha Ananthi J.")
    assert prefix == "Dr"
    assert norm == "Vijitha Ananthi J"
    assert fname == "Vijitha"
    assert lname == "Ananthi J"

    # Test no title
    prefix, norm, fname, lname, clean = parser._normalize_name("John Doe")
    assert prefix == ""
    assert norm == "John Doe"
    assert fname == "John"
    assert lname == "Doe"

def test_department_inference():
    parser = FacultyCSVParser("dummy.csv")
    
    assert parser._infer_department("kiran_cse@vignan.ac.in") == "CSE"
    assert parser._infer_department("abc_eee@vignan.ac.in") == "EEE"
    assert parser._infer_department("someone_mech@vignan.ac.in") == "MECH"
    assert parser._infer_department("rajumtech6@gmail.com") == "Unknown"
    assert parser._infer_department("dean@vignan.ac.in") == "Unknown"

def test_parse_list():
    parser = FacultyCSVParser("dummy.csv")
    
    assert parser._parse_list("Machine Learning | Data Mining") == ["Machine Learning", "Data Mining"]
    assert parser._parse_list(" ") == []
    assert parser._parse_list("Single Item") == ["Single Item"]
