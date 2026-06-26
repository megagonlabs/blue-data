###############
### DataSchema
#
class DataSchema:
    def __init__(self):
        """Initialize empty containers for entities and relations."""
        self.entities = {}
        self.relations = {}
        self.metadata = {}

    def has_entity(self, key):
        """
        Check if an entity exists in the schema.

        Parameters:
            key (str): The entity name or identifier.

        Returns:
            bool: True if the entity exists, False otherwise.
        """
        return key in self.entities

    def add_entity(self, key, description=None):
        """
        Add a new entity to the schema.

        If the entity already exists, a unique suffix is appended (e.g., "__1").

        Parameters:
            key (str): The name of the entity.
            description (str, optional): A description for the entity.

        Returns:
            str: The original entity key.
        """
        index = 0
        if key in self.entities:
            entity_obj = self.entities[key]
            index = entity_obj["index"] + 1
            entity_obj["index"] = index

        unique_key = key
        if index > 0:
            unique_key = key + "__" + str(index)

        if description is None:
            description = ""

        entity_obj = {
            'name': key,
            'index': index,
            'description': description,
            'created_by': None,
            'properties': {},  # type info only
            'contents': {'attributes': {}},  # hierarchical child info  # attributes
            'icon': None,
        }

        self.entities[unique_key] = entity_obj

        return key

    def add_entity_attribute(self, key, attribute, type, description=None):
        """
        Add an attribute to an existing entity.

        Parameters:
            key (str): The entity key.
            attribute (str): The name of the attribute.
            type (str): The type or description of the attribute.
            description (str, optional): A description for the attribute.
        """
        if key not in self.entities:
            return
        entity_obj = self.entities[key]

        if description is None:
            description = ""

        entity_obj['contents']['attributes'][attribute] = {
            'name': attribute,
            'info': type,
            'description': description,
        }

    def _relation_encoding(self, source, relation, target):
        """
        Create a unique encoded key for a relation.

        Parameters:
            source (str): The source entity name.
            relation (str): The relationship type.
            target (str): The target entity name.

        Returns:
            str: Encoded relation identifier string.
        """
        s = source + " " + relation + " " + target
        return s.replace(" ", "__")
        # return "(" + source + ")" + "-" + relation + "->" + "(" + target + ")"

    def has_relation(self, source, relation, target):
        """
        Check if a relation exists in the schema.

        Parameters:
            source (str): Source entity name.
            relation (str): Relation name.
            target (str): Target entity name.

        Returns:
            bool: True if the relation exists, False otherwise.
        """
        relation_encoding = self._relation_encoding(source, relation, target)
        return relation_encoding in self.relations

    def add_relation(self, source, relation, target, description=None):
        """
        Add a relation between two entities in the schema.

        If the same relation already exists, a numeric suffix is appended.

        Parameters:
            source (str): Source entity name.
            relation (str): Relation name.
            target (str): Target entity name.
            description (str, optional): A description for the relation.

        Returns:
            str: Unique key of the created relation.
        """
        key = self._relation_encoding(source, relation, target)
        index = 0
        if key in self.relations:
            relation_obj = self.relations[key]
            index = relation_obj["index"] + 1
            relation_obj["index"] = index

        unique_key = key
        if index > 0:
            unique_key = key + "__" + str(index)

        if description is None:
            description = ""

        relation_obj = {}
        relation_obj['name'] = relation
        relation_obj['index'] = index
        relation_obj['source'] = source
        relation_obj['target'] = target
        relation_obj['description'] = description
        relation_obj['properties'] = {}
        relation_obj['contents'] = {'attributes': {}}

        self.relations[unique_key] = relation_obj

        return unique_key

    def add_relation_attribute(self, key, attribute, type, description=None):
        """
        Add an attribute to an existing relation.

        Parameters:
            key (str): Relation key.
            attribute (str): Attribute name.
            type (str): Attribute type or description.
            description (str, optional): A description for the attribute.
        """
        if key not in self.relations:
            return
        relation_obj = self.relations[key]

        if description is None:
            description = ""

        relation_obj['contents']['attributes'][attribute] = {
            'name': attribute,
            'info': type,
            'description': description,
        }

    def get_entities(self):
        """
        Get all entities defined in the schema.

        Returns:
            dict: Mapping of entity keys to entity definitions.
        """
        return self.entities

    def get_relations(self):
        """
        Get all relations defined in the schema.

        Returns:
            dict: Mapping of relation keys to relation definitions.
        """
        return self.relations

    def to_json(self):
        """
        Convert the schema to a JSON-serializable dictionary.

        Returns:
            dict: Dictionary with 'entities' and 'relations' keys.
        """
        s = {}
        s['entities'] = self.entities.copy()
        s['relations'] = self.relations.copy()
        return s

    def __repr__(self):
        return "DataSchema()"

    def __str__(self):
        s = 'Schema:' + '\n'
        s += 'Entities: ' + '\n'
        for key in self.entities:
            entity_obj = self.entities[key]
            name = entity_obj['name']
            index = entity_obj['index']
            properties = entity_obj['properties']
            s += "key: " + key + '\n'
            s += "  name: " + name + '\n'
            s += "  description: " + entity_obj['description'] + '\n'
            s += "  index: " + str(index) + '\n'
            s += "  properties: " + '\n'
            for property in properties:
                prop_obj = properties[property]
                s += "    " + property + ": " + prop_obj['type'] + '\n'
                s += "      description: " + prop_obj['description'] + '\n'
            contents = entity_obj['contents'] if 'contents' in entity_obj else {}
            if 'attributes' in contents:
                attributes = contents['attributes']
                s += "  attributes: " + '\n'
                for attribute in attributes:
                    attr_obj = attributes[attribute]
                    s += "    " + attribute + ": " + attr_obj['info'] + '\n'
                    s += "      description: " + attr_obj['description'] + '\n'

        s += 'Relations: ' + '\n'
        for key in self.relations:
            relation_obj = self.relations[key]
            name = relation_obj['name']
            index = relation_obj['index']
            source = relation_obj['source']
            target = relation_obj['target']
            properties = relation_obj['properties']
            s += "key: " + key + '\n'
            s += "  name: " + name + '\n'
            s += "  description: " + relation_obj['description'] + '\n'
            s += "  index: " + str(index) + '\n'
            s += "  source: " + source + '\n'
            s += "  target: " + target + '\n'
            s += "  properties: " + '\n'
            for property in properties:
                prop_obj = properties[property]
                s += "    " + property + ": " + prop_obj['type'] + '\n'
                s += "      description: " + prop_obj['description'] + '\n'

            contents = relation_obj['contents'] if 'contents' in relation_obj else {}
            if 'attributes' in contents:
                attributes = contents['attributes']
                s += "  attributes: " + '\n'
                for attribute in attributes:
                    attr_obj = attributes[attribute]
                    s += "    " + attribute + ": " + attr_obj['info'] + '\n'
                    s += "      description: " + attr_obj['description'] + '\n'

        if self.metadata:
            s += 'Metadata: ' + '\n'
            for key in self.metadata:
                s += "  " + key + ": " + self.metadata[key] + '\n'

        return s
