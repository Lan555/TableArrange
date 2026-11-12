initial_schema = {
    "type" : "object",
    "properties":{
        "objects_on_table" : {
                "type" : "array",
                "items" : {
                    "type" : "object",
                    "properties" : {
                        "new_object_id": {
                            "type": "string",
                            "description" : "The id of the object, e.g. cup_1, book_1, laptop_1, etc."
                        },
                        "style" : {
                            "type" : "string",
                            "description" : "Style of the object"
                        },
                        "material" : {
                            "type" : "string",
                            "description" : "The material that this object is made of"
                        },
                        "size_in_meters" : {
                            "type": "object",
                            "properties": {
                                "length": {
                                    "type": "number"
                                },
                                "width": {
                                    "type": "number"
                                },
                                "height": {
                                    "type": "number"
                                }
                            },
                            "required" : ["length", "width", "height"]
                        },
                        "is_on_the_table" : {
                            "type"  : "boolean",
                            "description" : "Whether this object is touching the table surface"
                        },
                        "facing" : {
                            "type" : "string",
                            "description" : "The id of the object or table edge this object is facing, e.g. north_edge, book_1, laptop_1..."
                        },
                        "placement" : {
                            "type" : "object",
                            "description" : "The placement of the object on the table as a scene graph",
                            "properties" : {
                                "table_layout_elements" : {
                                    "type" : "array",
                                    "description" : "Scene Graph with the table layout elements such as edges or the middle of the table. E.g. The cup is on the north edge, the book is in the north-west corner...",
                                    "items" : {
                                        "type" : "object",
                                        "properties" : {
                                            "layout_element_id" : {
                                                "type" : "string",
                                                "description" : "The id of the layout element that this object is connected to, e.g. north_edge, west_edge, middle_of_table...",
                                                "enum" : ["north_edge", "south_edge", "west_edge", "east_edge", "middle_of_table"]
                                            },
                                            "preposition" : {
                                                "type" : "string",
                                                "description" : "The preposition that connects this object and the layout element, e.g. on the west edge, in the corner...",
                                                "enum" : ["on", "in the corner"]
                                            }
                                        },
                                        "required" : ["layout_element_id", "preposition"]
                                    }
                                },
                                "objects_on_table" : {
                                    "type" : "array",
                                    "description" : "Scene Graph with the other placed objects on the table. E.g. The cup is in front of the laptop, the pen is right of the notebook...",
                                    "items" : {
                                        "type" : "object",
                                        "properties" : {
                                            "object_id" : {
                                                "type" : "string",
                                                "description" : "The id of the object that this object is connected to, e.g. book_1, pen_1..."
                                            },
                                            "preposition" : {
                                                "type" : "string",
                                                "description" : "The preposition that connects this object and the connected object. 'new_object_id' is 'preposition' 'object_id'. E.g. pen_1 is left of book_1, cup_1 is behind laptop_1, eraser_1 is under notebook_1...",
                                                "enum" : ["on", "left of", "right of", "in front", "behind", "under", "above"]
                                            },
                                            "is_adjacent" : {
                                                "type" : "boolean",
                                                "description" : "Whether this object and the connected object are adjacent to each other, e.g. an object on the book is adjacent to the book."
                                            }
                                        }
                                    }
                                }
                            },
                            "required" : ["table_layout_elements", "objects_on_table"]
                        }
                    },
                    "required" : ["new_object_id", "style", "material", "size_in_meters", "is_on_the_table", "facing", "placement"]
                }
            }
        },
        "required" : ["objects_on_table"]
}

interior_designer_schema = """
{
    "Objects" : {
        "type" : "array",
        "items" : {
            "type" : "object"
        }
    },
    "required" : ["Objects"]
}
"""

interior_architect_schema = """
{
    "Placements" : {
        "type" : "array",
        "items" : {
            "type" : "object"
        }
    },
    "required" : ["Placements"]
}
"""

engineer_schema = """
{
    "objects_on_table" : {
        "type" : "array",
        "items" : {
            "type" : "object",
            "properties" : {
                "new_object_id": {
                    "type": "string",
                    "description" : "The lower-case id of the object, e.g. cup_1, book_1, laptop_1, etc."
                },
                "style" : {
                    "type" : "string",
                    "description" : "Style of the object"
                },
                "material" : {
                    "type" : "string",
                    "description" : "The material that this object is made of"
                },
                "size_in_meters" : {
                    "type": "object",
                    "properties": {
                        "length": {
                            "type": "number"
                        },
                        "width": {
                            "type": "number"
                        },
                        "height": {
                            "type": "number"
                        }
                    },
                    "required" : ["length", "width", "height"]
                },
                "is_on_the_table" : {
                    "type"  : "boolean",
                    "description" : "Whether this object is touching the table surface"
                },
                "facing" : {
                    "type" : "string",
                    "description" : "The id of the object or table edge this object is facing, e.g. north_edge, book_1, laptop_1..."
                },
                "placement" : {
                    "type" : "object",
                    "description" : "The placement of the object on the table as a scene graph",
                    "properties" : {
                        "table_layout_elements" : {
                            "type" : "array",
                            "description" : "Scene Graph with the table layout elements such as edges or the middle of the table. E.g. The cup is on the north edge, the book is in the north-west corner...",
                            "items" : {
                                "type" : "object",
                                "properties" : {
                                    "layout_element_id" : {
                                        "type" : "string",
                                        "description" : "The id of the layout element that this object is connected to, e.g. north_edge, west_edge, middle_of_table...",
                                        "enum" : ["north_edge", "south_edge", "west_edge", "east_edge", "middle_of_table"]
                                    },
                                    "preposition" : {
                                        "type" : "string",
                                        "description" : "The preposition that connects this object and the layout element, e.g. on the west edge, in the corner...",
                                        "enum" : ["on", "in the corner"]
                                    }
                                },
                                "required" : ["layout_element_id", "preposition"]
                            }
                        },
                        "objects_on_table" : {
                            "type" : "array",
                            "description" : "Scene Graph with the other placed objects on the table. E.g. The cup is in front of the laptop, the pen is right of the notebook...",
                            "items" : {
                                "type" : "object",
                                "properties" : {
                                    "object_id" : {
                                        "type" : "string",
                                        "description" : "The id of the object that this object is connected to, e.g. book_1, pen_1..."
                                    },
                                    "preposition" : {
                                        "type" : "string",
                                        "description" : "The preposition that connects the new_object_id and object_id objects in the following format: 'new_object_id' is 'preposition' 'object_id'. E.g. pen_1 is left of book_1, cup_1 is behind laptop_1, eraser_1 is under notebook_1...",
                                        "enum" : ["on", "left of", "right of", "in front", "behind", "under", "above"]
                                    },
                                    "is_adjacent" : {
                                        "type" : "boolean",
                                        "description" : "Whether this object and the connected object are adjacent to each other, e.g. an object on the book is adjacent to the book."
                                    }
                                }
                            }
                        }
                    },
                    "required" : ["table_layout_elements", "objects_on_table"]
                }
            },
            "required" : ["new_object_id", "style", "material", "size_in_meters", "is_on_the_table", "facing", "placement"]
        }
    },
    "required" : ["objects_on_table"]
}
"""

layout_corrector_schema = {
    "corrected_object" : {
        "type" : "object",
        "properties" : {
            "new_object_id": {
                "type": "string",
                "description" : "The id of the object, e.g. chair_1, table_1, bed_1, etc."
            },
            "is_on_the_table" : {
                "type"  : "boolean",
                "description" : "Whether the this object is touching the table"
            },
            "facing" : {
                "type" : "string",
                "description" : "The id of the object is this object facing, this has to be an object_id! Ex. north_edge, book_1, laptop_1..."
            },
            "placement" : {
                "type" : "object",
                "description" : "The placement of the object on the table as a scene graph",
                "properties" : {
                    "table_layout_elements" : {
                        "type" : "array",
                        "description" : "Scene Graph with the table layout elements such as edges or the middle of the table. E.g. The chair is on the north edge, the book is in the north-west corner...",
                        "items" : {
                            "type" : "object",
                            "properties" : {
                                "layout_element_id" : {
                                    "type" : "string",
                                    "description" : "The id of the layout element that this object is connected to, e.g. north_edge, west_edge, middle_of_table...",
                                    "enum" : ["north_edge", "south_edge", "west_edge", "east_edge", "middle_of_table"]
                                },
                                "preposition" : {
                                    "type" : "string",
                                    "description" : "The preposition that connects this object and the layout element, e.g. on the west edge, in the corner...",
                                    "enum" : ["on", "in the corner"]
                                }
                            },
                            "required" : ["layout_element_id", "preposition"]
                        }
                    },
                    "objects_on_table" : {
                        "type" : "array",
                        "description" : "Scene Graph with the other placed objects on the table. E.g. The chair is in front of the book, the plant is right of the notebook...",
                        "items" : {
                            "type" : "object",
                            "properties" : {
                                "object_id" : {
                                    "type" : "string",
                                    "description" : "The id of the object that this object is connected to, e.g. book_1, plant_1..."
                                },
                                "preposition" : {
                                    "type" : "string",
                                    "description" : "The preposition that connects this object and the connected object, e.g. left of the book, behind the plant, the notebook is under the book...",
                                    "enum" : ["on", "left of", "right of", "in front", "behind", "under", "above"]
                                },
                                "is_adjacent" : {
                                    "type" : "boolean",
                                    "description" : "Whether this object and the connected object are adjacent to each other, e.g. an object on the book is adjacent to the book."
                                }
                            }
                        }
                    }
                },
                "required" : ["table_layout_elements", "objects_on_table"]
            }
        }    
    }
}

deletion_schema = {
    "object_to_delete" : "desk_1"
}

layout_refiner_schema = {
    "type" : "object",
    "properties":{
        "children_objects" : {
            "type" : "array",
            "items" : {
                "type" : "object",
                "properties" : {
                    "name_id" : {
                        "type" : "string"
                    },
                    "placement" : {
                        "type" : "object",
                        "properties" : {
                            "children_objects" : {
                                "type" : "array",
                                "items" : {
                                    "type" : "object",
                                    "properties" : {
                                        "name_id" : {
                                            "type" : "string",
                                            "description" : "The name_id of the other child object"
                                        },
                                        "preposition" : {
                                            "type" : "string",
                                            "description" : "The preposition that connects this object and the connected object, ex. left of the desk, behind the plant, the rug is under the desk...",
                                            "enum" : ["on", "left of", "right of", "in front", "behind", "under", "above"]
                                        },
                                        "is_adjacent" : {
                                            "type" : "boolean",
                                            "description" : "Whether this object and the connected object are adjacent to each other, ex. an object on the desk is adjacent to the desk."
                                        }
                                    },
                                    "required" : ["name_id", "preposition", "is_adjacent"]
                                }
                            }
                        },
                        "required" : ["children_objects"]
                    }
                },
                "required" : ["name_id", "placement"]
            }
        },
    },
    "required" : ["children_objects"]
}