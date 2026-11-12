desktop_prompts = """You are an experienced indoor designer, you focus on optimizing space and arranging objects on the tabletop appropriately. Please assist me in crafting a tabletop. Each table is a rectangle. You need to define the four coordinates.
Note: the units for the coordinates are meters.
For example:
computer desk | [(0, 0), (0, 0.8), (0.5, 0.8), (0.5, 0)]
writing desk | [(0, 0), (0, 0.6), (0.4, 0.6), (0.4, 0)]

Here are some guidelines for you:
1. A table's size range (length or width) is 0.5m to 2m. The maximum area of a table is 4 m$^2$. Please provide a tabletop within this range and ensure the table is not too small or too large.
2. Desktop types include but are not limited to computer desk, writing desk, dining table, coffee table, study desk and bar table.

Now, I need a design for {input}.
Additional requirements: {additional_requirements}.
Your response should be direct and without additional text at the beginning or end."""

object_selection_prompt_1 =  """You are an experienced indoor designer, you focus on optimizing space and arranging objects on the tabletop appropriately, please assist me in selecting objects to decorate the table. You need to select appropriate objects to satisfy the customer's requirements.
You must provide a description and desired size for each object since I will use it to retrieve object. If multiple identical items are to be placed on the table, please indicate the quantity and variance type (same or varied).
Present your recommendations in JSON format:
{
    object_name:{
        "description": a short sentence describing the object,
        "size": the desired size of the object, in the format of a list of three numbers, [length, width, height] in centimeters,
        "quantity": the number of objects (int),
        "variance_type": "same" or "varied"
    }
}

For example:
{
    "Flower Vase":{
        "description": "A clear glass vase filled with fresh flowers, adding natural beauty and fragrance to the dining experience.",
        "size": [10, 10, 20],
        "quantity": 1,
        "variance_type": "same"
    },
    "Dinner Plates":{
        "description": "A set of four ceramic dinner plates in a neutral color, providing a stylish and functional base for meals.",
        "size": [20, 20, 2],
        "quantity": 2,
        "variance_type": "same"
    },
    "Wine Glasses":{
        "description": "A pair of crystal wine glasses, perfect for serving wine and adding a touch of sophistication to the table setting.",
        "size": [8, 8, 15],
        "quantity": 2,
        "variance_type": "same"
    },
    "Candlesticks":{
        "description": "A set of silver candlesticks with tapered candles, creating a warm and romantic atmosphere during dinner.",
        "size": [5, 5, 15],
        "quantity": 1,
        "variance_type": "same"
    }
}

Currently, we are working on the *TABLE_TYPE* with the size of TABLE_SIZE.
Please also consider the following additional requirements: {additional_requirements}.

Here are some guidelines for you:
1. Provide reasonable type/style/quantity of objects for each table based on the table size to make the table not too crowded or empty.
2. I want more types of objects on top of the table to make the table look more vivid.
3. Please do not use the general category of the objects. Please be more specific in the name of the objects.
4. Please choose objects that can be placed independently on the desktop, such as cups, computers, etc. Do not choose objects that are stacked or tablecloths.

Please first use natural language to explain your high-level design strategy for *TABLE_TYPE*, and then follow the desired JSON format *strictly* (do not add any additional text at the beginning or end)."""


object_selection_prompt_2 = """User: {object_selection_prompt_1}

Agent: {object_selection_1}

User: Thanks! After following your suggestions to retrieve objects, I found the *{table}* is still too empty. To enrich the *{table}*, you could:
1. Add more *types* of objects to the *{table}*.
2. Increase the size and quantity of the objects.
Could you update the entire JSON file with the same format as before and answer without additional text at the beginning or end?

Agent: """




object_constraints_prompt = """You are an experienced indoor designer, you focus on optimizing space and arranging objects on the tabletop appropriately.
Please help me arrange objects on the tabletop by assigning constraints to each object.
Here are the constraints and their definitions:
1. global constraint:
    1) edge: at the edge of the table.
    2) middle: not close to the edge of the table, most of the objects are placed here.

2. distance constraint:
    1) near, object: near to the other object, but with some distance, distance < 15cm.
    2) far, object: far away from the other object, distance >= 15cm.
    
3. position constraint:
    1) in front of, object: in front of another object.
    2) around, object: around another object, usually used for chairs.
    3) side of, object: on the side (left or right) of another object.
    4) left of, object: to the left of another object.
    5) right of, object: to the right of another object.

4. alignment constraint:
    1) center aligned, object: align the center of the object with the center of another object.

5. Rotation constraint:
    1) face to, object: face to the center of another object.

For each object, you must have one global constraint and you can select various numbers of constraints and any combinations of them and the output format must be:
object | global constraint | constraint 1 | constraint 2 | ...
For example:
Flower Vase | middle
Dinner Plates-0 | edge | far, Flower Vase | in front of, Flower Vase | center aligned, Flower Vase 
Dinner Plates-1 | edge | far, Flower Vase | in front of, Flower Vase | center aligned, Flower Vase
Wine Glasses-0 | edge | near, Dinner Plates-0 | side of, Dinner Plates-0 | center aligned, Dinner Plates-0
Wine Glasses-1 | edge | near, Dinner Plates-1 | side of, Dinner Plates-1 | center aligned, Dinner Plates-1 
Candlesticks | middle | far, Flower Vase | side of, Flower Vase | center aligned, Flower Vase

Here are some guidelines for you:
1. I will use your guideline to arrange the objects *iteratively*, so please start with an anchor object which doesn't depend on the other objects (with only one global constraint).
2. Place the larger objects first.
3. The latter objects could only depend on the former objects.
4. The objects of the *same type* are usually *aligned*.


Now I want you to design {table_type} and the table size is {table_size}.
Here are the objects that I want to place in the {table_type}:
{objects}
Please first use natural language to explain your high-level design strategy, and then follow the desired format *strictly* (do not add any additional text at the beginning or end) to provide the constraints for each object."""




desktop_baseline_prompt = """
You are an experienced indoor designer, you focus on optimizing space and arranging objects on the tabletop appropriately.

You operate in a 2D Space. You work in a X,Y coordinate system. (0, 0) denotes the bottom-left corner of the tabletop.
All objects should be placed in the positive quadrant. That is, coordinates of objects should be positive integer in centimeters.
Objects by default face +Y axis.
You answer by only generating JSON files that contain a list of the following information for each object:

- object_name: name of the object, follow the name strictly.
- position: coordinate of the object (center of the object bounding box) in the form of a dictionary, e.g. {{"X": 12, "Y": 20}}.
- rotation: the object rotation angle in clockwise direction when viewed by an observer looking along the z-axis towards the origin, e.g. 90. The default rotation is 0 which is +Y axis.

For example: {{"object_name": "Wine Glasses-0", "position": {{"X": 12, "Y": 20}}, "rotation": 90}}

Keep in mind, objects should be disposed in the area to create a meaningful layout. It is important that all objects provided are placed on the table.
Also keep in mind that the objects should be disposed all over the area in respect to the origin point of the area, and you can use negative values as well to display items correctly, since origin of the area is always at the center of the area.

Now I want you to design {table_type} and the table size is {table_size}.
Here are the objects (with their sizes) that I want to place in the {table_type}:
{objects}

Remember, you only generate JSON code, nothing else. It's very important. Respond in markdown (```).
"""