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

    def _max_entity_name_index(self, name):
        max_index = -1
        for entity_obj in self.entities.values():
            if entity_obj['name'] == name:
                max_index = max(max_index, entity_obj['index'])
        return max_index

    def add_entity(self, key, description=None, index=None):
        """
        Add a new entity to the schema.

        If the entity already exists, a unique suffix is appended (e.g., "__1").

        Parameters:
            key (str): The name of the entity.
            description (str, optional): A description for the entity.
            index (int, optional): Explicit index to use; auto-computed if not provided.

        Returns:
            str: The original entity key.
        """
        if index is None:
            index = self._max_entity_name_index(key) + 1
        unique_key = key if index == 0 else key + '__' + str(index)

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

    def _max_relation_name_index(self, source, relation, target):
        max_index = -1
        for rel_obj in self.relations.values():
            if rel_obj['source'] == source and rel_obj['name'] == relation and rel_obj['target'] == target:
                max_index = max(max_index, rel_obj['index'])
        return max_index

    def add_relation(self, source, relation, target, description=None, index=None):
        """
        Add a relation between two entities in the schema.

        If the same relation already exists, a numeric suffix is appended.

        Parameters:
            source (str): Source entity name.
            relation (str): Relation name.
            target (str): Target entity name.
            description (str, optional): A description for the relation.
            index (int, optional): Explicit index to use; auto-computed if not provided.

        Returns:
            str: Unique key of the created relation.
        """
        key = self._relation_encoding(source, relation, target)
        if index is None:
            index = self._max_relation_name_index(source, relation, target) + 1
        unique_key = key if index == 0 else key + '__' + str(index)

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

        relation_obj['properties'][attribute] = type
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

    @classmethod
    def from_json(cls, data):
        schema = cls()

        for entity_data in data.get('entities', {}).values():
            name = entity_data['name']
            index = entity_data.get('index')
            key = schema.add_entity(name, description=entity_data.get('description'), index=index)

            entity = schema.entities[key]
            if 'created_by' in entity_data:
                entity['created_by'] = entity_data['created_by']

            for attr_name, attr_obj in entity_data.get('contents', {}).get('attributes', {}).items():
                schema.add_entity_attribute(key, attr_name, attr_obj['info'], description=attr_obj.get('description'))

        for rel_data in data.get('relations', {}).values():
            index = rel_data.get('index')
            key = schema.add_relation(
                rel_data['source'], rel_data['name'], rel_data['target'],
                description=rel_data.get('description'),
                index=index,
            )
            rel = schema.relations[key]
            if 'created_by' in rel_data:
                rel['created_by'] = rel_data['created_by']

            for attr_name, attr_obj in rel_data.get('contents', {}).get('attributes', {}).items():
                schema.add_relation_attribute(key, attr_name, attr_obj['info'], description=attr_obj.get('description'))

        return schema

    def to_str(self, include_key=True, include_properties=True, include_index=True, simplified=False):
        """
        Convert the schema to a human-readable string with configurable verbosity.

        Parameters:
            include_key (bool): Include entity/relation keys. Ignored when simplified=True.
            include_properties (bool): Include properties block. Ignored when simplified=True.
            include_index (bool): Include index numbers. Ignored when simplified=True.
            simplified (bool): Compact one-line-per-item format that overrides other flags.

        Returns:
            str: Formatted schema string.
        """
        if simplified:
            lines = ["Schema:"]
            lines.append("Entities:")
            for key, entity_obj in self.entities.items():
                attrs = entity_obj['contents'].get('attributes', {})
                attr_parts = [f"{a}: {o['info']}" for a, o in attrs.items()]
                attr_str = f"{{{', '.join(attr_parts)}}}" if attr_parts else ""
                lines.append(f"  {entity_obj['name']}{' ' + attr_str if attr_str else ''}")
            lines.append("Relations:")
            for key, rel_obj in self.relations.items():
                attrs = rel_obj['contents'].get('attributes', {})
                attr_parts = [f"{a}: {o['info']}" for a, o in attrs.items()]
                attr_str = f"{{{', '.join(attr_parts)}}}" if attr_parts else ""
                lines.append(f"  ({rel_obj['source']}) -[{rel_obj['name']}{attr_str}]-> ({rel_obj['target']})")
            if self.metadata:
                lines.append("Metadata:")
                for k, v in self.metadata.items():
                    lines.append(f"  {k}: {v}")
            return "\n".join(lines) + "\n"

        s = "Schema:\n"
        s += "Entities:\n"
        for key, entity_obj in self.entities.items():
            name = entity_obj['name']
            if include_key:
                s += f"key: {key}\n"
                s += f"  name: {name}\n"
                s += f"  description: {entity_obj['description']}\n"
            else:
                s += f"{name}:\n"
                s += f"  description: {entity_obj['description']}\n"
            if include_index:
                s += f"  index: {entity_obj['index']}\n"
            if include_properties:
                properties = entity_obj['properties']
                s += "  properties:\n"
                for prop, prop_obj in properties.items():
                    s += f"    {prop}: {prop_obj['type']}\n"
                    s += f"      description: {prop_obj['description']}\n"
            attributes = entity_obj['contents'].get('attributes', {})
            if attributes:
                s += "  attributes:\n"
                for attr, attr_obj in attributes.items():
                    s += f"    {attr}: {attr_obj['info']}\n"
                    s += f"      description: {attr_obj['description']}\n"

        s += "Relations:\n"
        for key, rel_obj in self.relations.items():
            name = rel_obj['name']
            if include_key:
                s += f"key: {key}\n"
                s += f"  name: {name}\n"
                s += f"  description: {rel_obj['description']}\n"
            else:
                s += f"{name}:\n"
                s += f"  description: {rel_obj['description']}\n"
            if include_index:
                s += f"  index: {rel_obj['index']}\n"
            s += f"  source: {rel_obj['source']}\n"
            s += f"  target: {rel_obj['target']}\n"
            if include_properties:
                properties = rel_obj['properties']
                s += "  properties:\n"
                for prop, prop_obj in properties.items():
                    s += f"    {prop}: {prop_obj['type']}\n"
                    s += f"      description: {prop_obj['description']}\n"
            attributes = rel_obj['contents'].get('attributes', {})
            if attributes:
                s += "  attributes:\n"
                for attr, attr_obj in attributes.items():
                    s += f"    {attr}: {attr_obj['info']}\n"
                    s += f"      description: {attr_obj['description']}\n"

        if self.metadata:
            s += "Metadata:\n"
            for k, v in self.metadata.items():
                s += f"  {k}: {v}\n"

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
