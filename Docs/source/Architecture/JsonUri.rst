.. _arch_json_uri:

JSON URI syntax
===============

When a parameter's ``target`` is a ``.json`` file, the ``uri`` field is a list
of keys that traverses the nested JSON hierarchy.  Two special notations allow
searching inside JSON *lists* (arrays of objects):

``+["field"="value"]``
   Find the object in the list whose ``"field"`` equals ``"value"``.  The
   object **must** exist; raises an error if not found.

``*["field"="value"]``
   Find the object in the list whose ``"field"`` equals ``"value"``, **or
   create it** if absent.

``<chem_react>``
   Hint to the parser that ``value`` is a chombo-discharge chemical reaction
   string; comparison is semantic (ignores whitespace and ordering differences).
   See `"Specifying reactions" <https://chombo-discharge.github.io/chombo-discharge/Applications/CdrPlasmaModel.html?highlight=reaction#specifying-reactions>`_
   in the chombo-discharge documentation.

**Multiple parallel targets** -- when the second element of the uri list is
itself a list, the same traversal step applies to *all* entries in that inner
list simultaneously.  This is used to write two fields at the same time:

.. code-block:: python

   "uri": [
       "photoionization",
       [
           '+["reaction"=<chem_react>"Y + (O2) -> e + O2+"]',
           '*["reaction"=<chem_react>"Y + (O2) -> (null)"]'
       ],
       "efficiency"
   ],
   "values": [[1.0, 0.0]]

**Example 1** -- simple object search in a list:

.. code-block:: json

   {
       "parent": {
           "list-1": [
               {"field-name-0": "value_0"},
               {"field-name-1": {"target-field": "change-me!"}},
               {"field-name-2": "value_2"}
           ]
       }
   }

.. code-block:: python

   "uri" = [
       "parent",
       "list-1",
       '+["field-name-1"]',   # finds the container object
       "field-name-1",        # selects the child object
       "target-field"         # the actual target
   ]

**Example 2** -- searching by a specific value:

.. code-block:: json

   {
       "parent": {
           "list-level-1": [
               {"field-name-0": "value_0"},
               {"field-name-1": "value_1_0", "target-field": "dont-change-me!"},
               {"field-name-1": "value_1_1", "target-field": "change-me!"},
               {"field-name-2": "value_2"}
           ]
       }
   }

.. code-block:: python

   "uri" = [
       "parent",
       "list-level-1",
       '+["field-name-1"="value_1_1"]',   # finds the correct object
       "target-field"                      # the actual target
   ]

**Example 3** -- traversing two list levels:

.. code-block:: json

   {
       "parent": {
           "list-level-1": [
               {"field-name-1": "value_1_1",
                "target-field": [
                    {"search-field": "some-value", "target2-field": "dont-change!"},
                    {"search-field": "search-value", "target2-field": "change-me!"}
                ]}
           ]
       }
   }

.. code-block:: python

   "uri" = [
       "parent",
       "list-level-1",
       '+["field-name-1"="value_1_1"]',
       "target-field",
       '+["search-field"="search-value"]',
       "target2-field"
   ]

.. note::

   If searching for an object in a list where the search key is itself a JSON
   object, the value part can be omitted: ``+["field-name"]``.
