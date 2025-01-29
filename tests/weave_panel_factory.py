from polyfactory.factories import BaseFactory
import wandb_workspaces.reports.v2.internal as _wr


class WeavePanelFactory(BaseFactory):
    __model__ = _wr.WeavePanel

    @classmethod
    def is_supported_type(cls, model_type) -> bool:
        return model_type == _wr.WeavePanel

    @classmethod
    def build(cls, **kwargs) -> _wr.WeavePanel:
        config = kwargs.get("config", {})
        view_type = kwargs.get("view_type", "Weave")
        return _wr.WeavePanel(view_type=view_type, config=config)

    @classmethod
    def build_run_var_panel(cls):
        return cls.build(
            view_type="Weave",
            config={
                "panel2Config": {
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"run": "run"},
                                },
                                "value": "none",
                            },
                        },
                    }
                }
            },
        )

    @classmethod
    def build_summary_table_panel(cls):
        return cls.build(
            view_type="Weave",
            config={
                "panel2Config": {
                    "autoFocus": False,
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project",
                                        "filter": "string",
                                        "order": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "list",
                                "objectType": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                    "value": None,
                                },
                                "maxLength": 100,
                            },
                        },
                        "fromOp": {
                            "name": "pick",
                            "inputs": {
                                "obj": {
                                    "nodeType": "output",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string",
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string",
                                                },
                                            },
                                        },
                                        "value": {
                                            "type": "list",
                                            "objectType": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {"run": "run"},
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "_runtime": "float",
                                                        "_step": "int",
                                                        "_timestamp": "float",
                                                        "val/img_prediction_table": {
                                                            "type": "file",
                                                            "_base_type": {
                                                                "type": "FileBase"
                                                            },
                                                            "extension": "json",
                                                            "wbObjectType": {
                                                                "type": "table",
                                                                "_base_type": {
                                                                    "type": "Object"
                                                                },
                                                                "_is_object": True,
                                                                "_rows": {
                                                                    "type": "ArrowWeaveList",
                                                                    "_base_type": {
                                                                        "type": "list"
                                                                    },
                                                                    "objectType": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {},
                                                                    },
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                            "maxLength": 100,
                                        },
                                    },
                                    "fromOp": {
                                        "name": "run-summary",
                                        "inputs": {
                                            "run": {
                                                "nodeType": "var",
                                                "type": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "tagged",
                                                        "tag": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "entityName": "string",
                                                                "projectName": "string",
                                                            },
                                                        },
                                                        "value": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "project": "project",
                                                                "filter": "string",
                                                                "order": "string",
                                                            },
                                                        },
                                                    },
                                                    "value": {
                                                        "type": "list",
                                                        "objectType": "run",
                                                        "maxLength": 100,
                                                    },
                                                },
                                                "varName": "runs",
                                            }
                                        },
                                    },
                                },
                                "key": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": "table",
                                },
                            },
                        },
                    },
                },
                "isAuto": False,
            },
        )

    @classmethod
    def build_artifact_panel(cls):
        return cls.build(
            view_type="Weave",
            config={
                "panel2Config": {
                    "autoFocus": False,
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": "artifact",
                        },
                        "fromOp": {
                            "name": "project-artifact",
                            "inputs": {
                                "project": {
                                    "nodeType": "var",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string",
                                            },
                                        },
                                        "value": "project",
                                    },
                                    "varName": "project",
                                },
                                "artifactName": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": "run-nau48rpk-valimg_prediction_table",
                                },
                            },
                        },
                    },
                    "panelConfig": {
                        "selectedCollectionView": "versions",
                        "tabConfigs": {"overview": {}},
                    },
                    "panelInputType": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifact",
                    },
                }
            },
        )

    @classmethod
    def build_artifact_version_panel(cls):
        return cls.build(
            view_type="Weave",
            config={
                "panel2Config": {
                    "autoFocus": False,
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                        "artifactVersionAlias": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "file",
                                "_base_type": {"type": "FileBase"},
                                "extension": "json",
                                "wbObjectType": {
                                    "type": "table",
                                    "_base_type": {"type": "Object"},
                                    "_is_object": True,
                                    "_rows": {
                                        "type": "ArrowWeaveList",
                                        "_base_type": {"type": "list"},
                                        "objectType": {
                                            "type": "typedDict",
                                            "propertyTypes": {},
                                        },
                                    },
                                },
                            },
                        },
                        "fromOp": {
                            "name": "artifactVersion-file",
                            "inputs": {
                                "artifactVersion": {
                                    "nodeType": "output",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string",
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "artifactName": "string",
                                                    "artifactVersionAlias": "string",
                                                },
                                            },
                                        },
                                        "value": "artifactVersion",
                                    },
                                    "fromOp": {
                                        "name": "project-artifactVersion",
                                        "inputs": {
                                            "project": {
                                                "nodeType": "var",
                                                "type": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "entityName": "string",
                                                            "projectName": "string",
                                                        },
                                                    },
                                                    "value": "project",
                                                },
                                                "varName": "project",
                                            },
                                            "artifactName": {
                                                "nodeType": "const",
                                                "type": "string",
                                                "val": "run-nau48rpk-valimg_prediction_table",
                                            },
                                            "artifactVersionAlias": {
                                                "nodeType": "const",
                                                "type": "string",
                                                "val": "v0",
                                            },
                                        },
                                    },
                                },
                                "path": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": "val/img_prediction_table.table.json",
                                },
                            },
                        },
                    },
                    "panelInputType": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifact",
                    },
                }
            },
        )
