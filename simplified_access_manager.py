#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simplified Access Manager (Tkinter)
- Loads departments/positions and systems from data.json
- Lets you assign systems to a position (matrix) with checkboxes
- Generates HTML forms from the provided templates:
    * solicitud_template.html  (Access Request Form)
    * checklist_template.html  (IT Checklist - light fill of header fields)
    * departure_template.html  (Departure checklist - light fill of header fields)
- Saves generated files under ./generated-forms/<Employee Name>/
- Minimal "login": admin (read-write) / viewer (read-only)
"""
import json
import os
import hashlib
import calendar
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path

APP_TITLE = "Simplified Access Manager"
DATA_FILE = "data.json"
MATRIX_FILE = "matrix.json"
TEMPL_SOLICITUD = "solicitud_template.html"
TEMPL_CHECKLIST = "checklist_template.html"
TEMPL_DEPARTURE = "departure_template.html"
OUT_DIR = "generated-forms"

# ---- Helpers ----
def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
    except json.JSONDecodeError:
        messagebox.showerror("Error", f"Archivo JSON inválido: {path}")
        return default if default is not None else {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def center_window(window):
    """Center a window on the screen"""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')

# ---- Model ----
class Model:
    def __init__(self):
        self.data = load_json(DATA_FILE, {
            "departments": [],
            "systems": [],
            "categories": [],
            "roles": [],
            "users": [],
            "settings": {}
        })
        self.matrix = load_json(MATRIX_FILE, {})  # position_id -> [system_ids]
        self.settings = self.data.setdefault("settings", {})
        # index structures
        self.dept_by_id = {d["id"]: d for d in self.data.get("departments", [])}
        self.pos_by_id = {}
        for d in self.data.get("departments", []):
            for p in d.get("positions", []):
                self.pos_by_id[p["id"]] = {"dept_id": d["id"], **p}
        self.systems = self.data.get("systems", [])
        self.systems_by_id = {s["id"]: s for s in self.systems}
        self.categories = self.data.get("categories", [])
        self.categories_by_id = {c["id"]: c for c in self.categories}
        self.roles = self.data.get("roles", [])
        self.roles_by_id = {r["id"]: r for r in self.roles}
        self.users = self.data.get("users", [])
        self.users_by_username = {u["username"]: u for u in self.users}
        # group systems by categoryId (fallback label)
        self.systems_by_cat = {}
        for s in self.systems:
            self.systems_by_cat.setdefault(s.get("categoryId", 0), []).append(s)

    def get_generate_checked_only(self) -> bool:
        return bool(self.settings.get("generate_checked_only", False))

    def set_generate_checked_only(self, enabled: bool):
        self.settings["generate_checked_only"] = bool(enabled)
        self.data["settings"] = self.settings
        save_json(DATA_FILE, self.data)

    def get_departments(self):
        return self.data.get("departments", [])

    def get_positions_for_dept(self, dept_id):
        d = self.dept_by_id.get(dept_id)
        return d.get("positions", []) if d else []

    def get_all_positions(self):
        out = []
        for d in self.get_departments():
            for p in d.get("positions", []):
                out.append((d["name"], p))
        return out

    def systems_for_position(self, pos_id):
        # Convert string IDs to integers for consistency
        return set(int(sys_id) for sys_id in self.matrix.get(str(pos_id), []))

    def set_system_for_position(self, pos_id, sys_id, enabled):
        pos_key = str(pos_id)
        # Convert string IDs to integers for consistency
        current = set(int(id) for id in self.matrix.get(pos_key, []))
        if enabled:
            current.add(int(sys_id))
        else:
            current.discard(int(sys_id))
        self.matrix[pos_key] = sorted(current)
        save_json(MATRIX_FILE, self.matrix)

    # Category CRUD operations
    def get_categories(self):
        return self.categories

    def add_category(self, name):
        # Find the next available ID
        max_id = max([c["id"] for c in self.categories], default=0)
        new_id = max_id + 1
        new_category = {"id": new_id, "name": name}
        self.categories.append(new_category)
        self.categories_by_id[new_id] = new_category
        self.data["categories"] = self.categories
        save_json(DATA_FILE, self.data)
        return new_category

    def update_category(self, cat_id, name):
        if cat_id in self.categories_by_id:
            self.categories_by_id[cat_id]["name"] = name
            # Update in the list as well
            for cat in self.categories:
                if cat["id"] == cat_id:
                    cat["name"] = name
                    break
            self.data["categories"] = self.categories
            save_json(DATA_FILE, self.data)
            return True
        return False

    def delete_category(self, cat_id):
        if cat_id in self.categories_by_id:
            # Check if any systems are using this category
            systems_in_category = [s for s in self.systems if s.get("categoryId") == cat_id]
            if systems_in_category:
                return False, "Cannot delete category with systems. Move or delete systems first."
            
            # Remove from dict and list
            del self.categories_by_id[cat_id]
            self.categories = [c for c in self.categories if c["id"] != cat_id]
            self.data["categories"] = self.categories
            save_json(DATA_FILE, self.data)
            return True, "Category deleted successfully"
        return False, "Category not found"

    # System CRUD operations
    def get_systems(self):
        return self.systems

    def add_system(self, name, category_id):
        # Find the next available ID
        max_id = max([s["id"] for s in self.systems], default=0)
        new_id = max_id + 1
        new_system = {"id": new_id, "name": name, "categoryId": category_id}
        self.systems.append(new_system)
        self.systems_by_id[new_id] = new_system
        # Update systems_by_cat
        self.systems_by_cat.setdefault(category_id, []).append(new_system)
        self.data["systems"] = self.systems
        save_json(DATA_FILE, self.data)
        return new_system

    def update_system(self, sys_id, name, category_id):
        if sys_id in self.systems_by_id:
            old_category_id = self.systems_by_id[sys_id].get("categoryId")
            
            # Update system
            self.systems_by_id[sys_id]["name"] = name
            self.systems_by_id[sys_id]["categoryId"] = category_id
            
            # Update in the list as well
            for sys in self.systems:
                if sys["id"] == sys_id:
                    sys["name"] = name
                    sys["categoryId"] = category_id
                    break
            
            # Update systems_by_cat if category changed
            if old_category_id != category_id:
                # Remove from old category
                if old_category_id in self.systems_by_cat:
                    self.systems_by_cat[old_category_id] = [
                        s for s in self.systems_by_cat[old_category_id] if s["id"] != sys_id
                    ]
                    if not self.systems_by_cat[old_category_id]:
                        del self.systems_by_cat[old_category_id]
                
                # Add to new category
                self.systems_by_cat.setdefault(category_id, []).append(self.systems_by_id[sys_id])
            
            self.data["systems"] = self.systems
            save_json(DATA_FILE, self.data)
            return True
        return False

    def delete_system(self, sys_id):
        if sys_id in self.systems_by_id:
            system = self.systems_by_id[sys_id]
            category_id = system.get("categoryId")
            
            # Remove from dict and list
            del self.systems_by_id[sys_id]
            self.systems = [s for s in self.systems if s["id"] != sys_id]
            
            # Update systems_by_cat
            if category_id in self.systems_by_cat:
                self.systems_by_cat[category_id] = [
                    s for s in self.systems_by_cat[category_id] if s["id"] != sys_id
                ]
                if not self.systems_by_cat[category_id]:
                    del self.systems_by_cat[category_id]
            
            # Remove from all positions in matrix
            for pos_key in list(self.matrix.keys()):
                # Convert to integers for comparison
                pos_systems = [int(id) for id in self.matrix[pos_key]]
                if int(sys_id) in pos_systems:
                    self.matrix[pos_key].remove(str(sys_id))  # Keep as string for JSON storage
                    if not self.matrix[pos_key]:
                        del self.matrix[pos_key]
            
            self.data["systems"] = self.systems
            save_json(DATA_FILE, self.data)
            save_json(MATRIX_FILE, self.matrix)
            return True, "System deleted successfully"
        return False, "System not found"

    # Role management methods
    def get_roles(self):
        return self.roles

    def get_role_by_id(self, role_id):
        return self.roles_by_id.get(role_id)

    def add_role(self, role_id, name, description, permissions):
        if role_id in self.roles_by_id:
            return False, "Role ID already exists"
        
        new_role = {
            "id": role_id,
            "name": name,
            "description": description,
            "permissions": permissions
        }
        self.roles.append(new_role)
        self.roles_by_id[role_id] = new_role
        self.data["roles"] = self.roles
        save_json(DATA_FILE, self.data)
        return True, "Role created successfully"

    def update_role(self, role_id, name=None, description=None, permissions=None):
        if role_id not in self.roles_by_id:
            return False, "Role not found"
        
        role = self.roles_by_id[role_id]
        if name is not None:
            role["name"] = name
        if description is not None:
            role["description"] = description
        if permissions is not None:
            role["permissions"] = permissions
        
        # Update in the list as well
        for r in self.roles:
            if r["id"] == role_id:
                if name is not None:
                    r["name"] = name
                if description is not None:
                    r["description"] = description
                if permissions is not None:
                    r["permissions"] = permissions
                break
        
        self.data["roles"] = self.roles
        save_json(DATA_FILE, self.data)
        return True, "Role updated successfully"

    def delete_role(self, role_id):
        if role_id not in self.roles_by_id:
            return False, "Role not found"
        
        # Check if any users are using this role
        users_with_role = [u for u in self.users if u.get("role") == role_id]
        if users_with_role:
            return False, "Cannot delete role. Users are still assigned to this role."
        
        # Remove from dict and list
        del self.roles_by_id[role_id]
        self.roles = [r for r in self.roles if r["id"] != role_id]
        self.data["roles"] = self.roles
        save_json(DATA_FILE, self.data)
        return True, "Role deleted successfully"

    # User management methods
    def get_users(self):
        return self.users

    def get_user_by_username(self, username):
        return self.users_by_username.get(username)

    def authenticate_user(self, username, password):
        user = self.get_user_by_username(username)
        if user and user.get("active", True):
            stored_password = user.get("password", "")
            if stored_password == sha256(password) or stored_password == password:  # Support both hashed and plain text
                return user
        return None

    def add_user(self, username, password, name, role, active=True):
        if username in self.users_by_username:
            return False, "Username already exists"
        
        if role not in self.roles_by_id:
            return False, "Invalid role"
        
        new_user = {
            "id": max([u.get("id", 0) for u in self.users], default=0) + 1,
            "username": username,
            "password": sha256(password),  # Store hashed password
            "name": name,
            "role": role,
            "active": active
        }
        self.users.append(new_user)
        self.users_by_username[username] = new_user
        self.data["users"] = self.users
        save_json(DATA_FILE, self.data)
        return True, "User created successfully"

    def update_user(self, user_id, username=None, password=None, name=None, role=None, active=None):
        user = None
        for u in self.users:
            if u["id"] == user_id:
                user = u
                break
        
        if not user:
            return False, "User not found"
        
        old_username = user["username"]
        
        # Check for username conflict if changing username
        if username and username != old_username and username in self.users_by_username:
            return False, "Username already exists"
        
        # Check for valid role if changing role
        if role and role not in self.roles_by_id:
            return False, "Invalid role"
        
        # Update user data
        if username is not None:
            del self.users_by_username[old_username]
            user["username"] = username
            self.users_by_username[username] = user
        if password is not None:
            user["password"] = sha256(password)
        if name is not None:
            user["name"] = name
        if role is not None:
            user["role"] = role
        if active is not None:
            user["active"] = active
        
        self.data["users"] = self.users
        save_json(DATA_FILE, self.data)
        return True, "User updated successfully"

    def delete_user(self, user_id):
        user = None
        for i, u in enumerate(self.users):
            if u["id"] == user_id:
                user = u
                break
        
        if not user:
            return False, "User not found"
        
        # Remove from dict and list
        del self.users_by_username[user["username"]]
        self.users = [u for u in self.users if u["id"] != user_id]
        self.data["users"] = self.users
        save_json(DATA_FILE, self.data)
        return True, "User deleted successfully"

    def check_permission(self, user, resource, action):
        """Check if a user has permission for a specific action on a resource"""
        if not user:
            return False
        
        role_id = user.get("role")
        role = self.get_role_by_id(role_id)
        
        if not role:
            return False
        
        permissions = role.get("permissions", {})
        resource_permissions = permissions.get(resource, {})
        
        return resource_permissions.get(action, False)

# ---- Forms generation ----
class FormGenerator:
    @staticmethod
    def _set_input_value(html: str, input_id: str, value: str) -> str:
        """Insert or update the value attribute for an <input> with the given id."""
        if value is None:
            return html
        escaped = FormGenerator._escape_html(str(value))
        pattern = re.compile(rf'(<input\b[^>]*\bid="{input_id}"[^>]*)(>)', re.IGNORECASE)

        def repl(match):
            attrs = match.group(1)
            if "value=" in attrs:
                attrs = re.sub(r'value="[^"]*"', f'value="{escaped}"', attrs)
            else:
                attrs = attrs + f' value="{escaped}"'
            return attrs + match.group(2)

        return re.sub(pattern, repl, html, count=1)

    @staticmethod
    def _fill_basic_fields(
        html: str,
        employee_name: str,
        position_name: str,
        dept_name: str,
        *,
        date_value=None,
        date_label=None,
        onq_user=None,
        email=None,
    ) -> str:
        html = FormGenerator._set_input_value(html, "nombre", employee_name)
        html = FormGenerator._set_input_value(html, "posicion", position_name)
        html = FormGenerator._set_input_value(html, "departamento", dept_name)

        if date_label:
            html = html.replace("Fecha Ingreso", date_label, 1)
        if not date_value:
            date_value = datetime.now().strftime("%d-%b-%y")
        html = FormGenerator._set_input_value(html, "fecha_ingreso", date_value)

        if onq_user:
            html = FormGenerator._set_input_value(html, "idm_login", onq_user)
        if email:
            html = FormGenerator._set_input_value(html, "email", email)
        return html

    @staticmethod
    def _escape_html(text: str) -> str:
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;"))

    @staticmethod
    def _render_system_sections(systems_by_cat, checked_ids, categories_by_id=None):
        # Create minimal Tailwind-ish blocks similar to template style
        blocks = []
        for cat_id in sorted(systems_by_cat.keys()):
            systems = systems_by_cat[cat_id]
            rows = []
            for s in systems:
                checked = "checked" if s["id"] in checked_ids else ""
                rows.append(
                    '''<label class="flex items-center gap-2">
    <input type="checkbox" {checked} style="height: var(--checkbox-size); width: var(--checkbox-size);" />
    <span>{name}</span>
</label>'''.format(checked=checked, name=FormGenerator._escape_html(s["name"]))
                )
            
            # Get the actual category name if available
            cat_name = f"Categoría {cat_id}"
            if categories_by_id and cat_id in categories_by_id:
                cat_name = categories_by_id[cat_id].get("name", cat_name)
                
            block = '''
<div>
  <h4 class="bg-blue-900 text-white font-bold p-2 rounded" style="font-size: var(--text-section-header);">{cat_name}</h4>
  <div class="grid grid-cols-2 gap-1 p-2" style="font-size: var(--text-checkbox);">
    {rows}
  </div>
</div>'''.format(cat_name=cat_name, rows="".join(rows))
            blocks.append(block)
        return "\n".join(blocks)

    @staticmethod
    def _render_departure_systems(model: Model, checked_ids):
        # Group assigned systems by category for the departure checklist
        systems_by_category = {}
        for sys_id in sorted(checked_ids):
            system = model.systems_by_id.get(sys_id)
            if not system:
                continue
            cat_id = system.get("categoryId", 0)
            systems_by_category.setdefault(cat_id, []).append(system)

        if not systems_by_category:
            return '<p class="col-span-3 italic text-gray-600">No systems assigned for this position.</p>'

        blocks = []
        for cat_id in sorted(systems_by_category.keys()):
            systems = systems_by_category[cat_id]
            systems.sort(key=lambda s: s.get("name", "").lower())

            cat_name = model.categories_by_id.get(cat_id, {}).get("name")
            if not cat_name:
                cat_name = "Uncategorized" if cat_id == 0 else f"Category {cat_id}"
            cat_name = FormGenerator._escape_html(cat_name)

            labels = []
            for system in systems:
                labels.append(
                    '''<label class="flex items-center gap-2">
        <input type="checkbox" checked style="height: var(--checkbox-size); width: var(--checkbox-size);" />
        <span>{name}</span>
    </label>'''.format(name=FormGenerator._escape_html(system.get("name", "")))
                )

            block = '''
<div class="space-y-2">
  <h4 class="font-bold text-gray-900" style="font-size: var(--text-section-header);">{cat_name}</h4>
  <div class="space-y-1" style="font-size: var(--text-checkbox);">
    {labels}
  </div>
</div>'''.format(cat_name=cat_name, labels="\n    ".join(labels))
            blocks.append(block)

        return "\n".join(blocks)

    @classmethod
    def make_new_hire_forms(
        cls,
        model: Model,
        employee_name: str,
        dept_id: int,
        pos_id: int,
        *,
        onq_user="",
        email="",
        date_value=None,
        date_label=None,
    ):
        pos = model.pos_by_id.get(pos_id, {"name": ""})
        dept = model.dept_by_id.get(dept_id, {"name": ""})
        checked = model.systems_for_position(pos_id)
        # Ensure checked is a set of integers
        if not isinstance(checked, set):
            checked = set()
        if model.get_generate_checked_only():
            # Only include systems that belong to the position when requested
            filtered_by_cat = {}
            for cat_id, systems in model.systems_by_cat.items():
                filtered = [s for s in systems if s["id"] in checked]
                if filtered:
                    filtered_by_cat[cat_id] = filtered
            systems_by_category = filtered_by_cat
        else:
            systems_by_category = model.systems_by_cat

        # --- Access Request (solicitud) ---
        solicitud_html = read_text(TEMPL_SOLICITUD)
        solicitud_html = cls._fill_basic_fields(
            solicitud_html,
            employee_name,
            pos.get("name", ""),
            dept.get("name", ""),
            date_value=date_value,
            date_label=date_label,
            onq_user=onq_user,
            email=email,
        )
        # inject dynamic systems
        systems_block = cls._render_system_sections(systems_by_category, checked, model.categories_by_id)
        solicitud_html = solicitud_html.replace("<!-- DYNAMIC_SYSTEM_SECTIONS_PLACEHOLDER -->", systems_block)

        # --- IT Checklist (checklist) ---
        checklist_html = read_text(TEMPL_CHECKLIST)
        checklist_html = cls._fill_basic_fields(
            checklist_html,
            employee_name,
            pos.get("name", ""),
            dept.get("name", ""),
            date_value=date_value,
            date_label=date_label,
        )
        
        # Generate dynamic system rows for the checklist
        system_rows = []
        for cat_id in sorted(systems_by_category.keys()):
            systems = systems_by_category[cat_id]
            for system in systems:
                # Ensure system["id"] and checked are both integers for comparison
                system_id = int(system["id"])
                checked_status = "checked" if system_id in checked else ""
                row = '''
<tr>
    <td class="px-4 py-6 whitespace-nowrap font-medium text-gray-900" style="font-size: var(--text-form-label);">
        {system_name}
    </td>
    <td class="px-4 py-6 whitespace-nowrap border-l-2 border-gray-400">
        <label class="flex items-center justify-center">
            <input type="checkbox" {checked} style="height: var(--checkbox-size); width: var(--checkbox-size);" class="text-blue-600 border-gray-400 rounded">
        </label>
    </td>
    <td class="px-2 py-6 border-l-2 border-gray-400">
        <!-- Anotaciones section without textbox -->
    </td>
</tr>'''.format(system_name=FormGenerator._escape_html(system["name"]), checked=checked_status)
                system_rows.append(row)
        
        # Replace the placeholder with the dynamic system rows
        checklist_html = checklist_html.replace("<!-- DYNAMIC_SYSTEM_ROWS_PLACEHOLDER -->", "".join(system_rows))

        # Paths
        folder = Path(OUT_DIR) / employee_name.strip().replace(os.sep, "_")
        os.makedirs(folder, exist_ok=True)
        out_solicitud = folder / f"{employee_name} - Solicitud de Acceso.html"
        out_checklist = folder / f"{employee_name} - IT Checklist.html"

        write_text(out_solicitud.as_posix(), solicitud_html)
        write_text(out_checklist.as_posix(), checklist_html)
        return out_solicitud.as_posix(), out_checklist.as_posix()

    @classmethod
    def make_departure_form(
        cls,
        model: Model,
        employee_name: str,
        dept_id: int,
        pos_id: int,
        *,
        onq_user="",
        email="",
        date_value=None,
    ):
        pos = model.pos_by_id.get(pos_id, {"name": ""})
        dept = model.dept_by_id.get(dept_id, {"name": ""})
        html = read_text(TEMPL_DEPARTURE)
        html = cls._set_input_value(html, "departure_employee", employee_name)
        html = cls._set_input_value(html, "departure_position", pos.get("name", ""))
        html = cls._set_input_value(html, "departure_department", dept.get("name", ""))
        html = cls._set_input_value(html, "departure_onq", onq_user)

        if date_value:
            html = cls._set_input_value(html, "departure_term_date", date_value)
            html = cls._set_input_value(html, "departure_remove_access", date_value)
            html = cls._set_input_value(html, "departure_process_date", date_value)
        today_fmt = datetime.now().strftime("%d-%b-%y")
        html = cls._set_input_value(html, "departure_today", today_fmt)

        # Build the network & applications section using the systems assigned to the position
        checked = model.systems_for_position(pos_id)
        network_html = cls._render_departure_systems(model, checked)
        html = html.replace("<!-- Content for this section would be dynamically populated or added here -->", network_html)

        folder = Path(OUT_DIR) / employee_name.strip().replace(os.sep, "_")
        os.makedirs(folder, exist_ok=True)
        out_file = folder / f"{employee_name} - Separation Checklist.html"
        write_text(out_file.as_posix(), html)
        return out_file.as_posix()

class DatePickerDialog(tk.Toplevel):
    def __init__(self, master, initial_date=None, on_select=None):
        super().__init__(master)
        self.title("Seleccionar fecha")
        self.transient(master)
        self.resizable(False, False)
        self.on_select = on_select
        base_date = initial_date or datetime.now()
        self.year = base_date.year
        self.month = base_date.month

        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)

        nav = ttk.Frame(container)
        nav.pack(fill="x")
        ttk.Button(nav, text="◀", width=3, command=self._prev_month).pack(side="left")
        self.lbl_month = ttk.Label(nav, text="", anchor="center")
        self.lbl_month.pack(side="left", expand=True)
        ttk.Button(nav, text="▶", width=3, command=self._next_month).pack(side="right")

        header = ttk.Frame(container)
        header.pack(fill="x", pady=(4, 0))
        for idx, day_name in enumerate(["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]):
            ttk.Label(header, text=day_name, width=3, anchor="center").grid(row=0, column=idx, padx=1)

        self.days_frame = ttk.Frame(container)
        self.days_frame.pack(pady=(2, 0))

        action_frame = ttk.Frame(container)
        action_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(action_frame, text="Cerrar", command=self._on_close).pack(side="right")

        self._draw_calendar()
        self.after(10, lambda: center_window(self))

    def _draw_calendar(self):
        for child in self.days_frame.winfo_children():
            child.destroy()
        month_name = calendar.month_name[self.month]
        self.lbl_month.configure(text=f"{month_name} {self.year}")
        cal = calendar.Calendar(firstweekday=0)
        for row_idx, week in enumerate(cal.monthdayscalendar(self.year, self.month)):
            for col_idx, day in enumerate(week):
                if day == 0:
                    ttk.Label(self.days_frame, text="", width=3).grid(row=row_idx, column=col_idx, padx=1, pady=1)
                    continue
                btn = ttk.Button(
                    self.days_frame,
                    text=f"{day:02d}",
                    width=3,
                    command=lambda d=day: self._select_day(d),
                )
                btn.grid(row=row_idx, column=col_idx, padx=1, pady=1)

    def _prev_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self._draw_calendar()

    def _next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self._draw_calendar()

    def _select_day(self, day):
        selected = datetime(self.year, self.month, day)
        if self.on_select:
            self.on_select(selected)
        self._on_close()

    def _on_close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

# ---- View / Controller ----
class LoginWindow(tk.Toplevel):
    def __init__(self, master, model, on_login):
        super().__init__(master)
        self.title(f"{APP_TITLE} - Login")
        self.resizable(False, False)
        self.model = model
        self.on_login = on_login

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0, sticky="nsew")
        
        # Center the login window
        self.after(100, lambda: center_window(self))

        ttk.Label(frm, text="Username").grid(row=0, column=0, sticky="w")
        self.e_user = ttk.Entry(frm, width=24)
        self.e_user.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(frm, text="Password").grid(row=1, column=0, sticky="w")
        self.e_pass = ttk.Entry(frm, width=24, show="*")
        self.e_pass.grid(row=1, column=1, sticky="ew", pady=4)

        btn = ttk.Button(frm, text="Login", command=self._submit)
        btn.grid(row=2, column=0, columnspan=2, pady=8)

        self.bind("<Return>", lambda e: self._submit())

    def _submit(self):
        username = self.e_user.get().strip()
        password = self.e_pass.get()
        
        user = self.model.authenticate_user(username, password)
        if user:
            self.on_login(user)
            self.destroy()
        else:
            messagebox.showerror("Login", "Invalid username or password.")

class MatrixTab(ttk.Frame):
    def __init__(self, master, model: Model, user=None):
        super().__init__(master)
        self.model = model
        self.user = user
        self.read_only = not model.check_permission(user, "access_matrix", "edit")
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left: positions list
        left = ttk.Frame(self, padding=(8,8,4,8))
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="Puestos").pack(anchor="w")
        self.pos_list = tk.Listbox(left, width=35, height=20, exportselection=False)
        self.pos_list.pack(fill="both", expand=True)
        self.pos_list.bind("<<ListboxSelect>>", self._on_select_position)

        # Populate positions grouped by dept
        self._pos_index = []  # (dept_id, pos_id)
        for dept in self.model.get_departments():
            self.pos_list.insert("end", f"— {dept['name']} —")
            self.pos_list.itemconfig("end", foreground="#777")
            self._pos_index.append((None, None))
            for p in dept.get("positions", []):
                self.pos_list.insert("end", f"  {p['name']}")
                self._pos_index.append((dept["id"], p["id"]))

        # Right: systems checkboxes (grouped by categoryId)
        right = ttk.Frame(self, padding=(4,8,8,8))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        canvas = tk.Canvas(right, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        inner = ttk.Frame(canvas)

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_configure)
        canvas.create_window((0,0), window=inner, anchor="nw")

        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            # Windows: event.delta is 120 per scroll step
            # Positive delta = scroll up, negative = scroll down
            delta = -1 * (event.delta / 120)
            canvas.yview_scroll(int(delta), "units")
        
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", _bind_to_mousewheel)
        canvas.bind("<Leave>", _unbind_from_mousewheel)

        self.vars = {}  # sys_id -> tk.IntVar
        self.category_frames = {}  # Store category frames for horizontal layout
        
        # Create a container for horizontal layout
        categories_container = ttk.Frame(inner)
        categories_container.pack(fill="both", expand=True)
        
        # Track current position for horizontal layout
        current_row = 0
        current_col = 0
        max_cols = 3  # Maximum number of categories per row
        
        for cat_id in sorted(self.model.systems_by_cat.keys()):
            # Get the actual category name
            cat_name = self.model.categories_by_id.get(cat_id, {}).get("name", f"Categoría {cat_id}")
            
            # Create category frame with border
            cat_frame = ttk.LabelFrame(categories_container, text=cat_name, padding=(8, 4))
            cat_frame.grid(row=current_row, column=current_col, sticky="nsew", padx=5, pady=5)
            self.category_frames[cat_id] = cat_frame
            
            # Configure grid weights for proper resizing
            categories_container.grid_columnconfigure(current_col, weight=1)
            categories_container.grid_rowconfigure(current_row, weight=1)
            
            # Create a frame for the checkboxes within this category
            checkbox_frame = ttk.Frame(cat_frame)
            checkbox_frame.pack(fill="both", expand=True)
            
            # Create checkboxes in a grid layout (2 columns)
            col = 0
            row = 0
            for s in sorted(self.model.systems_by_cat[cat_id], key=lambda x: x["name"]):
                var = tk.IntVar(value=0)
                self.vars[s["id"]] = var
                cb = ttk.Checkbutton(checkbox_frame, text=s["name"], variable=var,
                                     state=("disabled" if self.read_only else "normal"),
                                     command=self._on_toggle)
                cb.grid(row=row, column=col, sticky="w", padx=4, pady=2)
                col = 1 - col
                if col == 0:
                    row += 1
            
            # Update position for next category
            current_col += 1
            if current_col >= max_cols:
                current_col = 0
                current_row += 1

        self._current_pos = None

    def _on_select_position(self, *_):
        idx = self.pos_list.curselection()
        if not idx:
            return
        di, pi = self._pos_index[idx[0]]
        # ignore dept header rows
        if pi is None:
            return
        self._current_pos = pi
        # load states
        selected = self.model.systems_for_position(pi)
        for sid, var in self.vars.items():
            var.set(1 if sid in selected else 0)

    def _on_toggle(self):
        if self._current_pos is None:
            return
        # save all toggles in one pass to avoid many writes
        for sid, var in self.vars.items():
            self.model.set_system_for_position(self._current_pos, sid, bool(var.get()))

class GenerateTab(ttk.Frame):
    DATE_INPUT_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%y", "%d-%b-%Y")
    DATE_LABELS = {
        "ingreso": "Fecha de Ingreso",
        "modificacion": "Fecha de Modificación",
        "retiro": "Fecha de Retiro",
    }

    def __init__(self, master, model: Model, user=None):
        super().__init__(master)
        self.user = user
        self.model = model
        self.model = model
        self.onq_var = tk.StringVar()
        self.email_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.date_mode = tk.StringVar(value="ingreso")
        self._date_picker = None
        self._build_ui()

    def _build_ui(self):
        pad = 8
        frm = ttk.Frame(self, padding=pad)
        frm.pack(fill="x", expand=False)

        # Employee field
        ttk.Label(frm, text="Empleado").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.e_name = ttk.Entry(frm, width=25)
        self.e_name.grid(row=0, column=1, sticky="w", pady=(0, 4), padx=(4, 0))

        # Department field
        ttk.Label(frm, text="Departamento").grid(row=1, column=0, sticky="w", pady=(0, 4))
        self.cmb_dept = ttk.Combobox(frm, state="readonly", width=23)
        self.cmb_dept.grid(row=1, column=1, sticky="w", pady=(0, 4), padx=(4, 0))

        # Position field
        ttk.Label(frm, text="Puesto").grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.cmb_pos = ttk.Combobox(frm, state="readonly", width=23)
        self.cmb_pos.grid(row=2, column=1, sticky="w", pady=(0, 4), padx=(4, 0))

        # OnQ User field
        ttk.Label(frm, text="Usuario OnQ").grid(row=3, column=0, sticky="w", pady=(0, 4))
        self.e_onq = ttk.Entry(frm, width=25, textvariable=self.onq_var)
        self.e_onq.grid(row=3, column=1, sticky="w", pady=(0, 4), padx=(4, 0))

        # Email field
        ttk.Label(frm, text="Correo electrónico").grid(row=4, column=0, sticky="w", pady=(0, 4))
        self.e_email = ttk.Entry(frm, width=25, textvariable=self.email_var)
        self.e_email.grid(row=4, column=1, sticky="w", pady=(0, 4), padx=(4, 0))

        # Date field
        ttk.Label(frm, text="Fecha").grid(row=5, column=0, sticky="w", pady=(0, 4))
        date_frame = ttk.Frame(frm)
        date_frame.grid(row=5, column=1, sticky="ew", pady=(0, 4), padx=(4, 0))
        
        self.e_date = ttk.Entry(date_frame, width=18, textvariable=self.date_var)
        self.e_date.pack(side="left")
        
        self.btn_date = ttk.Button(date_frame, text="Seleccionar…", command=self._open_date_picker)
        self.btn_date.pack(side="left", padx=(4, 0))

        # Date type radio buttons
        radio_frame = ttk.Frame(frm)
        radio_frame.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Radiobutton(
            radio_frame, text="Fecha de ingreso", value="ingreso", variable=self.date_mode
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            radio_frame, text="Fecha de modificación", value="modificacion", variable=self.date_mode
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            radio_frame, text="Fecha de retiro", value="retiro", variable=self.date_mode
        ).pack(side="left")

        # Buttons
        button_frame = ttk.Frame(frm)
        button_frame.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))
        
        self.btn_hire = ttk.Button(button_frame, text="Generate New Hire Forms", command=self._gen_hire)
        self.btn_hire.pack(side="left", padx=(0, 8))
        
        self.btn_dep = ttk.Button(button_frame, text="Generate Departure Form", command=self._gen_departure)
        self.btn_dep.pack(side="left")

        # Configure grid weights
        # Removed weight=1 to prevent textboxes from expanding

        # populate departments
        self.dept_list = self.model.get_departments()
        self.cmb_dept["values"] = [d["name"] for d in self.dept_list]
        self.cmb_dept.bind("<<ComboboxSelected>>", self._on_dept_change)

        self.status = ttk.Label(self, text="", anchor="w", justify="left")
        self.status.pack(fill="x", padx=pad, pady=(0, pad))

    def _open_date_picker(self):
        if self._date_picker and self._date_picker.winfo_exists():
            return
        initial = self._parse_date_silent()
        picker = DatePickerDialog(self, initial_date=initial, on_select=self._on_date_selected)
        self._date_picker = picker
        self.wait_window(picker)
        self._date_picker = None

    def _on_date_selected(self, date_obj: datetime):
        self.date_var.set(date_obj.strftime("%Y-%m-%d"))

    def _parse_date_silent(self):
        text = self.date_var.get().strip()
        if not text:
            return None
        for fmt in self.DATE_INPUT_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def _require_date(self):
        parsed = self._parse_date_silent()
        if parsed:
            return parsed
        messagebox.showwarning(
            "Fecha inválida",
            "Introduce una fecha válida (ej. 2024-07-15) o selecciónala con el botón 'Seleccionar…'.",
        )
        return None

    def _on_dept_change(self, *_):
        name = self.cmb_dept.get()
        dept = next((d for d in self.dept_list if d["name"] == name), None)
        self.pos_list = self.model.get_positions_for_dept(dept["id"]) if dept else []
        self.cmb_pos["values"] = [p["name"] for p in self.pos_list]
        if self.pos_list:
            self.cmb_pos.current(0)

    def _require_inputs(self):
        employee = self.e_name.get().strip()
        dept_name = self.cmb_dept.get().strip()
        pos_name = self.cmb_pos.get().strip()
        if not employee or not dept_name or not pos_name:
            messagebox.showwarning("Missing info", "Please fill Employee, Department and Position.")
            return None
        dept = next((d for d in self.dept_list if d["name"] == dept_name), None)
        pos = next((p for p in self.pos_list if p["name"] == pos_name), None)
        if not dept or not pos:
            messagebox.showerror("Error", "Invalid department/position.")
            return None
        return employee, dept, pos

    def _gen_hire(self):
        req = self._require_inputs()
        if not req:
            return
        employee, dept, pos = req
        if self.date_mode.get() == "retiro":
            messagebox.showwarning("Modo incorrecto", "Selecciona una fecha de ingreso o modificación para generar estos formularios.")
            return
        date_obj = self._require_date()
        if not date_obj:
            return
        formatted_date = date_obj.strftime("%d-%b-%y")
        date_label = self.DATE_LABELS.get(self.date_mode.get(), self.DATE_LABELS["ingreso"])
        onq_user = self.onq_var.get().strip()
        email = self.email_var.get().strip()
        out1, out2 = FormGenerator.make_new_hire_forms(
            self.model,
            employee,
            dept["id"],
            pos["id"],
            onq_user=onq_user,
            email=email,
            date_value=formatted_date,
            date_label=date_label,
        )
        self.status.configure(text=f"Saved:\n- {out1}\n- {out2}")
        messagebox.showinfo("Done", "New hire forms created.\nYou can open the HTML files in a browser and Print to PDF.")

    def _gen_departure(self):
        req = self._require_inputs()
        if not req:
            return
        employee, dept, pos = req
        if self.date_mode.get() != "retiro":
            messagebox.showwarning("Modo incorrecto", "Selecciona la opción 'Fecha de retiro' para generar el formulario de salida.")
            return
        date_obj = self._require_date()
        if not date_obj:
            return
        formatted_date = date_obj.strftime("%d-%b-%y")
        onq_user = self.onq_var.get().strip()
        email = self.email_var.get().strip()
        out = FormGenerator.make_departure_form(
            self.model,
            employee,
            dept["id"],
            pos["id"],
            onq_user=onq_user,
            email=email,
            date_value=formatted_date,
        )
        self.status.configure(text=f"Saved:\n- {out}")
        messagebox.showinfo("Done", "Departure form created.\nOpen the HTML file in a browser and Print to PDF.")

class CategorySystemTab(ttk.Frame):
    def __init__(self, master, model: Model, user=None):
        super().__init__(master)
        self.model = model
        self.user = user
        self.read_only = not model.check_permission(user, "staff_management", "edit")
        self.selected_category_id = None
        self._build_ui()

    def _build_ui(self):
        # Main container with left-right layout
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Left side - Categories
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))
        
        # Categories header with CRUD button
        cat_header_frame = ttk.Frame(left_frame)
        cat_header_frame.pack(fill="x", pady=(0, 8))
        
        ttk.Label(cat_header_frame, text="Categories", font=("TkDefaultFont", 10, "bold")).pack(side="left")
        
        self.cat_crud_btn = ttk.Button(cat_header_frame, text="Manage Categories", command=self._open_category_crud)
        self.cat_crud_btn.pack(side="right", padx=(8, 0))
        
        if self.read_only:
            self.cat_crud_btn.config(state="disabled")
        
        # Categories listbox with scrollbar
        cat_list_frame = ttk.Frame(left_frame)
        cat_list_frame.pack(fill="both", expand=True)
        
        cat_scrollbar = ttk.Scrollbar(cat_list_frame)
        cat_scrollbar.pack(side="right", fill="y")
        
        self.cat_listbox = tk.Listbox(cat_list_frame, yscrollcommand=cat_scrollbar.set, exportselection=False)
        self.cat_listbox.pack(side="left", fill="both", expand=True)
        cat_scrollbar.config(command=self.cat_listbox.yview)
        
        self.cat_listbox.bind("<<ListboxSelect>>", self._on_category_select)
        
        # Right side - Systems for selected category
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(4, 0))
        
        # Systems header with CRUD button
        sys_header_frame = ttk.Frame(right_frame)
        sys_header_frame.pack(fill="x", pady=(0, 8))
        
        ttk.Label(sys_header_frame, text="Systems", font=("TkDefaultFont", 10, "bold")).pack(side="left")
        
        self.sys_crud_btn = ttk.Button(sys_header_frame, text="Manage Systems", command=self._open_system_crud, state="disabled")
        self.sys_crud_btn.pack(side="right", padx=(8, 0))
        
        if self.read_only:
            self.sys_crud_btn.config(state="disabled")
        
        # Systems listbox with scrollbar
        sys_list_frame = ttk.Frame(right_frame)
        sys_list_frame.pack(fill="both", expand=True)
        
        sys_scrollbar = ttk.Scrollbar(sys_list_frame)
        sys_scrollbar.pack(side="right", fill="y")
        
        self.sys_listbox = tk.Listbox(sys_list_frame, yscrollcommand=sys_scrollbar.set, exportselection=False)
        self.sys_listbox.pack(side="left", fill="both", expand=True)
        sys_scrollbar.config(command=self.sys_listbox.yview)
        
        self.sys_listbox.bind("<<ListboxSelect>>", self._on_system_select)
        
        # Populate categories
        self._refresh_categories()
        
        # Initialize empty systems list
        self._refresh_systems_for_category()

    def _refresh_categories(self):
        self.cat_listbox.delete(0, "end")
        self.cat_index = []  # Store category IDs
        for cat in self.model.get_categories():
            self.cat_listbox.insert("end", cat["name"])
            self.cat_index.append(cat["id"])

    def _refresh_systems_for_category(self):
        self.sys_listbox.delete(0, "end")
        self.sys_index = []  # Store system IDs
        
        if self.selected_category_id is None:
            return
        
        # Show only systems for the selected category
        for sys in self.model.get_systems():
            if sys.get("categoryId") == self.selected_category_id:
                self.sys_listbox.insert("end", sys["name"])
                self.sys_index.append(sys["id"])

    def _on_category_select(self, event):
        selection = self.cat_listbox.curselection()
        if not selection:
            self.selected_category_id = None
            self.sys_crud_btn.config(state="disabled")
            return
        
        idx = selection[0]
        self.selected_category_id = self.cat_index[idx]
        
        # Enable systems CRUD button when a category is selected
        if not self.read_only:
            self.sys_crud_btn.config(state="normal")
        
        # Refresh systems list to show only systems for this category
        self._refresh_systems_for_category()

    def _on_system_select(self, event):
        # This is now just for selection, no details panel needed
        pass

    def _open_category_crud(self):
        # Create a new window for category CRUD operations
        self.cat_crud_window = tk.Toplevel(self)
        self.cat_crud_window.title("Manage Categories")
        self.cat_crud_window.geometry("400x500")
        self.cat_crud_window.resizable(False, False)
        
        # Center the window
        self.cat_crud_window.after(100, lambda: center_window(self.cat_crud_window))
        
        # Category details
        ttk.Label(self.cat_crud_window, text="Category Details", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        
        details_frame = ttk.Frame(self.cat_crud_window)
        details_frame.pack(fill="x", padx=16, pady=(0, 16))
        
        ttk.Label(details_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=4)
        self.cat_name_entry = ttk.Entry(details_frame, width=30)
        self.cat_name_entry.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))
        
        # Categories list
        ttk.Label(self.cat_crud_window, text="Existing Categories", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=16, pady=(0, 8))
        
        list_frame = ttk.Frame(self.cat_crud_window)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.crud_cat_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, exportselection=False)
        self.crud_cat_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.crud_cat_listbox.yview)
        
        self.crud_cat_listbox.bind("<<ListboxSelect>>", self._on_crud_category_select)
        
        # Buttons
        button_frame = ttk.Frame(self.cat_crud_window)
        button_frame.pack(fill="x", padx=16, pady=(0, 16))
        
        self.cat_add_btn = ttk.Button(button_frame, text="Add", command=self._add_category)
        self.cat_add_btn.pack(side="left", padx=(0, 8))
        
        self.cat_update_btn = ttk.Button(button_frame, text="Update", command=self._update_category, state="disabled")
        self.cat_update_btn.pack(side="left", padx=(0, 8))
        
        self.cat_delete_btn = ttk.Button(button_frame, text="Delete", command=self._delete_category, state="disabled")
        self.cat_delete_btn.pack(side="left")
        
        # Populate categories
        self._refresh_crud_categories()

    def _open_system_crud(self):
        # Create a new window for system CRUD operations
        self.sys_crud_window = tk.Toplevel(self)
        self.sys_crud_window.title(f"Manage Systems for Category {self.model.categories_by_id[self.selected_category_id]['name']}")
        self.sys_crud_window.geometry("450x500")
        self.sys_crud_window.resizable(False, False)
        
        # Center the window
        self.sys_crud_window.after(100, lambda: center_window(self.sys_crud_window))
        
        # System details
        ttk.Label(self.sys_crud_window, text="System Details", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        
        details_frame = ttk.Frame(self.sys_crud_window)
        details_frame.pack(fill="x", padx=16, pady=(0, 16))
        
        ttk.Label(details_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=4)
        self.sys_name_entry = ttk.Entry(details_frame, width=30)
        self.sys_name_entry.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))
        
        ttk.Label(details_frame, text="Category:").grid(row=1, column=0, sticky="w", pady=4)
        self.sys_category_combo = ttk.Combobox(details_frame, state="readonly", width=28)
        self.sys_category_combo.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))
        
        # Set current category as default
        if self.selected_category_id in self.model.categories_by_id:
            self.sys_category_combo.set(self.model.categories_by_id[self.selected_category_id]["name"])
        
        # Systems list
        ttk.Label(self.sys_crud_window, text="Existing Systems", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=16, pady=(0, 8))
        
        list_frame = ttk.Frame(self.sys_crud_window)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.crud_sys_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, exportselection=False)
        self.crud_sys_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.crud_sys_listbox.yview)
        
        self.crud_sys_listbox.bind("<<ListboxSelect>>", self._on_crud_system_select)
        
        # Buttons
        button_frame = ttk.Frame(self.sys_crud_window)
        button_frame.pack(fill="x", padx=16, pady=(0, 16))
        
        self.sys_add_btn = ttk.Button(button_frame, text="Add", command=self._add_system)
        self.sys_add_btn.pack(side="left", padx=(0, 8))
        
        self.sys_update_btn = ttk.Button(button_frame, text="Update", command=self._update_system, state="disabled")
        self.sys_update_btn.pack(side="left", padx=(0, 8))
        
        self.sys_delete_btn = ttk.Button(button_frame, text="Delete", command=self._delete_system, state="disabled")
        self.sys_delete_btn.pack(side="left")
        
        # Populate systems and categories
        self._refresh_crud_systems()
        self._refresh_category_combo()

    def _refresh_crud_categories(self):
        if hasattr(self, 'crud_cat_listbox'):
            self.crud_cat_listbox.delete(0, "end")
            self.crud_cat_index = []  # Store category IDs
            for cat in self.model.get_categories():
                self.crud_cat_listbox.insert("end", cat["name"])
                self.crud_cat_index.append(cat["id"])

    def _refresh_crud_systems(self):
        if hasattr(self, 'crud_sys_listbox'):
            self.crud_sys_listbox.delete(0, "end")
            self.crud_sys_index = []  # Store system IDs
            
            # Show only systems for the selected category
            for sys in self.model.get_systems():
                if sys.get("categoryId") == self.selected_category_id:
                    self.crud_sys_listbox.insert("end", sys["name"])
                    self.crud_sys_index.append(sys["id"])

    def _refresh_category_combo(self):
        if hasattr(self, 'sys_category_combo'):
            categories = self.model.get_categories()
            self.sys_category_combo["values"] = [cat["name"] for cat in categories]

    def _on_crud_category_select(self, event):
        selection = self.crud_cat_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        cat_id = self.crud_cat_index[idx]
        category = self.model.categories_by_id.get(cat_id)
        
        if category:
            self.cat_name_entry.delete(0, "end")
            self.cat_name_entry.insert(0, category["name"])
            
            if not self.read_only:
                self.cat_update_btn.config(state="normal")
                self.cat_delete_btn.config(state="normal")

    def _on_crud_system_select(self, event):
        selection = self.crud_sys_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        sys_id = self.crud_sys_index[idx]
        system = self.model.systems_by_id.get(sys_id)
        
        if system:
            self.sys_name_entry.delete(0, "end")
            self.sys_name_entry.insert(0, system["name"])
            
            cat_id = system.get("categoryId")
            if cat_id and cat_id in self.model.categories_by_id:
                self.sys_category_combo.set(self.model.categories_by_id[cat_id]["name"])
            
            if not self.read_only:
                self.sys_update_btn.config(state="normal")
                self.sys_delete_btn.config(state="normal")

    def _add_category(self):
        name = self.cat_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Invalid Input", "Category name cannot be empty.")
            return
        
        self.model.add_category(name)
        self._refresh_categories()
        self._refresh_crud_categories()
        self.cat_name_entry.delete(0, "end")
        messagebox.showinfo("Success", "Category added successfully.")

    def _update_category(self):
        selection = self.crud_cat_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        cat_id = self.crud_cat_index[idx]
        name = self.cat_name_entry.get().strip()
        
        if not name:
            messagebox.showwarning("Invalid Input", "Category name cannot be empty.")
            return
        
        if self.model.update_category(cat_id, name):
            self._refresh_categories()
            self._refresh_crud_categories()
            self._refresh_crud_systems()  # Refresh systems to show updated category names
            # Only refresh category combo if the system CRUD window is open
            if hasattr(self, 'sys_category_combo') and self.sys_category_combo.winfo_exists():
                self._refresh_category_combo()
            messagebox.showinfo("Success", "Category updated successfully.")
        else:
            messagebox.showerror("Error", "Failed to update category.")

    def _delete_category(self):
        selection = self.crud_cat_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        cat_id = self.crud_cat_index[idx]
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this category?"):
            success, message = self.model.delete_category(cat_id)
            if success:
                self._refresh_categories()
                self._refresh_crud_categories()
                # Only refresh category combo if the system CRUD window is open
                if hasattr(self, 'sys_category_combo') and self.sys_category_combo.winfo_exists():
                    self._refresh_category_combo()
                self.cat_name_entry.delete(0, "end")
                self.cat_update_btn.config(state="disabled")
                self.cat_delete_btn.config(state="disabled")
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

    def _add_system(self):
        name = self.sys_name_entry.get().strip()
        cat_name = self.sys_category_combo.get()
        
        if not name:
            messagebox.showwarning("Invalid Input", "System name cannot be empty.")
            return
        
        if not cat_name:
            messagebox.showwarning("Invalid Input", "Please select a category.")
            return
        
        # Find category ID from name
        cat_id = None
        for cat in self.model.get_categories():
            if cat["name"] == cat_name:
                cat_id = cat["id"]
                break
        
        if cat_id is None:
            messagebox.showerror("Error", "Invalid category selected.")
            return
        
        self.model.add_system(name, cat_id)
        self._refresh_systems_for_category()
        self._refresh_crud_systems()
        self.sys_name_entry.delete(0, "end")
        messagebox.showinfo("Success", "System added successfully.")

    def _update_system(self):
        selection = self.crud_sys_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        sys_id = self.crud_sys_index[idx]
        name = self.sys_name_entry.get().strip()
        cat_name = self.sys_category_combo.get()
        
        if not name:
            messagebox.showwarning("Invalid Input", "System name cannot be empty.")
            return
        
        if not cat_name:
            messagebox.showwarning("Invalid Input", "Please select a category.")
            return
        
        # Find category ID from name
        cat_id = None
        for cat in self.model.get_categories():
            if cat["name"] == cat_name:
                cat_id = cat["id"]
                break
        
        if cat_id is None:
            messagebox.showerror("Error", "Invalid category selected.")
            return
        
        if self.model.update_system(sys_id, name, cat_id):
            self._refresh_systems_for_category()
            self._refresh_crud_systems()
            messagebox.showinfo("Success", "System updated successfully.")
        else:
            messagebox.showerror("Error", "Failed to update system.")

    def _delete_system(self):
        selection = self.crud_sys_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        sys_id = self.crud_sys_index[idx]
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this system? This will also remove it from all positions."):
            success, message = self.model.delete_system(sys_id)
            if success:
                self._refresh_systems_for_category()
                self._refresh_crud_systems()
                self.sys_name_entry.delete(0, "end")
                self.sys_update_btn.config(state="disabled")
                self.sys_delete_btn.config(state="disabled")
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

class ConfigurationsTab(ttk.Frame):
    def __init__(self, master, model: Model, user=None):
        super().__init__(master)
        self.model = model
        self.user = user
        self.read_only = not model.check_permission(user, "system_settings", "edit")
        self._build_ui()

    def _build_ui(self):
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Adjust application features that affect generated forms."
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        self._only_checked_var = tk.BooleanVar(value=self.model.get_generate_checked_only())
        self._only_checked_chk = ttk.Checkbutton(
            container,
            text="Generate new hire form and show only checked systems",
            variable=self._only_checked_var,
            command=self._on_toggle_only_checked
        )
        self._only_checked_chk.grid(row=1, column=0, sticky="w")

        if self.read_only:
            self._only_checked_chk.state(["disabled"])

    def _on_toggle_only_checked(self):
        self.model.set_generate_checked_only(self._only_checked_var.get())

class AccessControlTab(ttk.Frame):
    def __init__(self, master, model: Model, user=None):
        super().__init__(master)
        self.model = model
        self.user = user
        self.read_only = not model.check_permission(user, "role_management", "edit")
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        ttk.Label(header_frame, text="Role Management", font=("TkDefaultFont", 12, "bold")).pack(side="left")

        # Main content
        main_frame = ttk.Frame(self)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Roles list
        roles_frame = ttk.LabelFrame(main_frame, text="Roles")
        roles_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        roles_frame.columnconfigure(0, weight=1)
        roles_frame.rowconfigure(0, weight=1)

        # Treeview for roles
        columns = ("Name", "Description")
        self.roles_tree = ttk.Treeview(roles_frame, columns=columns, show="tree headings")
        self.roles_tree.heading("#0", text="ID")
        self.roles_tree.heading("Name", text="Name")
        self.roles_tree.heading("Description", text="Description")
        
        self.roles_tree.column("#0", width=100)
        self.roles_tree.column("Name", width=150)
        self.roles_tree.column("Description", width=200)
        
        self.roles_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.roles_tree.bind("<<TreeviewSelect>>", self._on_role_select)

        # Scrollbar
        roles_scroll = ttk.Scrollbar(roles_frame, orient="vertical", command=self.roles_tree.yview)
        roles_scroll.grid(row=0, column=1, sticky="ns", pady=5)
        self.roles_tree.configure(yscrollcommand=roles_scroll.set)

        # Permissions frame
        perm_frame = ttk.LabelFrame(main_frame, text="Permissions")
        perm_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        perm_frame.columnconfigure(0, weight=1)
        perm_frame.rowconfigure(1, weight=1)

        # Permission resources
        resources = ["access_matrix", "staff_management", "form_generation", "user_management", "role_management", "system_settings"]
        actions = ["view", "edit", "delete"]
        
        self.permission_vars = {}
        
        for i, resource in enumerate(resources):
            ttk.Label(perm_frame, text=resource.replace("_", " ").title()).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            
            for j, action in enumerate(actions):
                var = tk.BooleanVar()
                cb = ttk.Checkbutton(perm_frame, text=action.capitalize(), variable=var, 
                                   state="disabled" if self.read_only else "normal")
                cb.grid(row=i, column=j+1, padx=5, pady=2)
                self.permission_vars[(resource, action)] = var

        # Buttons
        if not self.read_only:
            btn_frame = ttk.Frame(perm_frame)
            btn_frame.grid(row=len(resources), column=0, columnspan=4, pady=10)
            
            ttk.Button(btn_frame, text="Add Role", command=self._add_role).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Update Role", command=self._update_role).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Delete Role", command=self._delete_role).pack(side="left", padx=5)

        self._load_roles()

    def _load_roles(self):
        # Clear existing items
        for item in self.roles_tree.get_children():
            self.roles_tree.delete(item)
        
        # Load roles
        for role in self.model.get_roles():
            self.roles_tree.insert("", "end", iid=role["id"], text=role["id"], 
                                 values=(role["name"], role["description"]))

    def _on_role_select(self, event):
        selection = self.roles_tree.selection()
        if not selection:
            return
        
        role_id = selection[0]
        role = self.model.get_role_by_id(role_id)
        
        if role:
            permissions = role.get("permissions", {})
            for (resource, action), var in self.permission_vars.items():
                var.set(permissions.get(resource, {}).get(action, False))

    def _add_role(self):
        dialog = RoleDialog(self, "Add Role", self.model)
        self.wait_window(dialog)
        if dialog.result:
            role_id, name, description, permissions = dialog.result
            success, message = self.model.add_role(role_id, name, description, permissions)
            if success:
                self._load_roles()
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

    def _update_role(self):
        selection = self.roles_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a role to update")
            return
        
        role_id = selection[0]
        role = self.model.get_role_by_id(role_id)
        
        if not role:
            return
        
        # Get current permissions
        permissions = {}
        for (resource, action), var in self.permission_vars.items():
            if resource not in permissions:
                permissions[resource] = {}
            permissions[resource][action] = var.get()
        
        dialog = RoleDialog(self, "Update Role", self.model, role)
        if dialog.result:
            new_role_id, name, description, new_permissions = dialog.result
            success, message = self.model.update_role(role_id, name, description, new_permissions)
            if success:
                self._load_roles()
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

    def _delete_role(self):
        selection = self.roles_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a role to delete")
            return
        
        role_id = selection[0]
        role = self.model.get_role_by_id(role_id)
        
        if not role:
            return
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete role '{role['name']}'?"):
            success, message = self.model.delete_role(role_id)
            if success:
                self._load_roles()
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

class UserManagementTab(ttk.Frame):
    def __init__(self, master, model: Model, user=None):
        super().__init__(master)
        self.model = model
        self.user = user
        self.read_only = not model.check_permission(user, "user_management", "edit")
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        ttk.Label(header_frame, text="User Management", font=("TkDefaultFont", 12, "bold")).pack(side="left")

        # Main content
        main_frame = ttk.Frame(self)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Users list
        users_frame = ttk.LabelFrame(main_frame, text="Users")
        users_frame.grid(row=0, column=0, sticky="nsew")
        users_frame.columnconfigure(0, weight=1)
        users_frame.rowconfigure(0, weight=1)

        # Treeview for users
        columns = ("Username", "Name", "Role", "Active")
        self.users_tree = ttk.Treeview(users_frame, columns=columns, show="tree headings")
        self.users_tree.heading("#0", text="ID")
        self.users_tree.heading("Username", text="Username")
        self.users_tree.heading("Name", text="Name")
        self.users_tree.heading("Role", text="Role")
        self.users_tree.heading("Active", text="Active")
        
        self.users_tree.column("#0", width=50)
        self.users_tree.column("Username", width=120)
        self.users_tree.column("Name", width=150)
        self.users_tree.column("Role", width=100)
        self.users_tree.column("Active", width=60)
        
        self.users_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Scrollbar
        users_scroll = ttk.Scrollbar(users_frame, orient="vertical", command=self.users_tree.yview)
        users_scroll.grid(row=0, column=1, sticky="ns", pady=5)
        self.users_tree.configure(yscrollcommand=users_scroll.set)

        # Buttons
        if not self.read_only:
            btn_frame = ttk.Frame(self)
            btn_frame.grid(row=2, column=0, pady=10)
            
            ttk.Button(btn_frame, text="Add User", command=self._add_user).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Edit User", command=self._edit_user).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Change Password", command=self._change_password).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Delete User", command=self._delete_user).pack(side="left", padx=5)

        self._load_users()

    def _load_users(self):
        # Clear existing items
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        
        # Load users
        for user in self.model.get_users():
            self.users_tree.insert("", "end", iid=user["id"], text=user["id"], 
                                 values=(user["username"], user["name"], user["role"], "Yes" if user.get("active", True) else "No"))

    def _add_user(self):
        dialog = UserDialog(self, "Add User", self.model)
        self.wait_window(dialog)
        if dialog.result:
            username, password, name, role, active = dialog.result
            success, message = self.model.add_user(username, password, name, role, active)
            if success:
                self._load_users()
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

    def _edit_user(self):
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user to edit")
            return
        
        user_id = int(selection[0])
        user = None
        for u in self.model.get_users():
            if u["id"] == user_id:
                user = u
                break
        
        if not user:
            return
        
        dialog = UserDialog(self, "Edit User", self.model, user)
        self.wait_window(dialog)
        if dialog.result:
            username, password, name, role, active = dialog.result
            success, message = self.model.update_user(user_id, username, password, name, role, active)
            if success:
                self._load_users()
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

    def _change_password(self):
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user to change password")
            return
        
        user_id = int(selection[0])
        user = None
        for u in self.model.get_users():
            if u["id"] == user_id:
                user = u
                break
        
        if not user:
            return
        
        dialog = PasswordDialog(self, f"Change Password for {user['username']}", user)
        self.wait_window(dialog)  # Wait for dialog to close
        if dialog.result:
            new_password = dialog.result
            success, message = self.model.update_user(user_id, None, new_password, None, None, None)
            if success:
                messagebox.showinfo("Success", "Password changed successfully")
            else:
                messagebox.showerror("Error", message)

    def _delete_user(self):
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user to delete")
            return
        
        user_id = int(selection[0])
        user = None
        for u in self.model.get_users():
            if u["id"] == user_id:
                user = u
                break
        
        if not user:
            return
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user '{user['name']}'?"):
            success, message = self.model.delete_user(user_id)
            if success:
                self._load_users()
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

class RoleDialog(tk.Toplevel):
    def __init__(self, master, title, model, role=None):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.model = model
        self.role = role
        self.result = None

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0, sticky="nsew")

        # Role ID
        ttk.Label(frm, text="Role ID:").grid(row=0, column=0, sticky="w", pady=2)
        self.role_id_var = tk.StringVar(value=role["id"] if role else "")
        self.role_id_entry = ttk.Entry(frm, textvariable=self.role_id_var, width=30)
        self.role_id_entry.grid(row=0, column=1, sticky="ew", pady=2)
        if role:  # Disable editing ID for existing roles
            self.role_id_entry.config(state="disabled")

        # Name
        ttk.Label(frm, text="Name:").grid(row=1, column=0, sticky="w", pady=2)
        self.name_var = tk.StringVar(value=role["name"] if role else "")
        ttk.Entry(frm, textvariable=self.name_var, width=30).grid(row=1, column=1, sticky="ew", pady=2)

        # Description
        ttk.Label(frm, text="Description:").grid(row=2, column=0, sticky="w", pady=2)
        self.desc_var = tk.StringVar(value=role["description"] if role else "")
        ttk.Entry(frm, textvariable=self.desc_var, width=30).grid(row=2, column=1, sticky="ew", pady=2)

        # Permissions
        ttk.Label(frm, text="Permissions:").grid(row=3, column=0, sticky="nw", pady=10)
        
        perm_frame = ttk.Frame(frm)
        perm_frame.grid(row=3, column=1, sticky="ew", pady=10)
        
        resources = ["access_matrix", "staff_management", "form_generation", "user_management", "role_management", "system_settings"]
        actions = ["view", "edit", "delete"]
        
        self.permission_vars = {}
        
        for i, resource in enumerate(resources):
            ttk.Label(perm_frame, text=resource.replace("_", " ").title()).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            
            for j, action in enumerate(actions):
                var = tk.BooleanVar()
                if role:
                    var.set(role.get("permissions", {}).get(resource, {}).get(action, False))
                cb = ttk.Checkbutton(perm_frame, text=action.capitalize(), variable=var)
                cb.grid(row=i, column=j+1, padx=5, pady=2)
                self.permission_vars[(resource, action)] = var

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="OK", command=self._ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        center_window(self)

    def _ok(self):
        role_id = self.role_id_var.get().strip()
        name = self.name_var.get().strip()
        description = self.desc_var.get().strip()
        
        if not role_id or not name:
            messagebox.showerror("Error", "Role ID and Name are required")
            return
        
        # Get permissions
        permissions = {}
        for (resource, action), var in self.permission_vars.items():
            if resource not in permissions:
                permissions[resource] = {}
            permissions[resource][action] = var.get()
        
        self.result = (role_id, name, description, permissions)
        self.destroy()

class PasswordDialog(tk.Toplevel):
    def __init__(self, master, title, user):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.user = user
        self.result = None

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0, sticky="nsew")

        # Username (read-only)
        ttk.Label(frm, text="Username:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(frm, text=user["username"]).grid(row=0, column=1, sticky="w", pady=2)

        # New Password
        ttk.Label(frm, text="New Password:").grid(row=1, column=0, sticky="w", pady=2)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(frm, textvariable=self.password_var, width=30, show="*")
        password_entry.grid(row=1, column=1, sticky="ew", pady=2)

        # Confirm Password
        ttk.Label(frm, text="Confirm Password:").grid(row=2, column=0, sticky="w", pady=2)
        self.confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(frm, textvariable=self.confirm_var, width=30, show="*")
        confirm_entry.grid(row=2, column=1, sticky="ew", pady=2)

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Change Password", command=self._ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        center_window(self)

    def _ok(self):
        password = self.password_var.get()
        confirm = self.confirm_var.get()
        
        if not password:
            messagebox.showerror("Error", "Password cannot be empty")
            return
        
        if password != confirm:
            messagebox.showerror("Error", "Passwords do not match")
            return
        
        if len(password) < 4:
            messagebox.showerror("Error", "Password must be at least 4 characters long")
            return
        
        self.result = password
        self.destroy()

class UserDialog(tk.Toplevel):
    def __init__(self, master, title, model, user=None):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.model = model
        self.user = user
        self.result = None

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0, sticky="nsew")

        # Username
        ttk.Label(frm, text="Username:").grid(row=0, column=0, sticky="w", pady=2)
        self.username_var = tk.StringVar(value=user["username"] if user else "")
        ttk.Entry(frm, textvariable=self.username_var, width=30).grid(row=0, column=1, sticky="ew", pady=2)

        # Password
        ttk.Label(frm, text="Password:").grid(row=1, column=0, sticky="w", pady=2)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(frm, textvariable=self.password_var, width=30, show="*")
        password_entry.grid(row=1, column=1, sticky="ew", pady=2)
        if not user:  # Password required for new users
            ttk.Label(frm, text="(required)", foreground="gray").grid(row=1, column=2, sticky="w", pady=2)
        else:  # Optional for existing users
            ttk.Label(frm, text="(leave blank to keep current)", foreground="gray").grid(row=1, column=2, sticky="w", pady=2)

        # Name
        ttk.Label(frm, text="Full Name:").grid(row=2, column=0, sticky="w", pady=2)
        self.name_var = tk.StringVar(value=user["name"] if user else "")
        ttk.Entry(frm, textvariable=self.name_var, width=30).grid(row=2, column=1, sticky="ew", pady=2)

        # Role
        ttk.Label(frm, text="Role:").grid(row=3, column=0, sticky="w", pady=2)
        self.role_var = tk.StringVar(value=user["role"] if user else "")
        role_combo = ttk.Combobox(frm, textvariable=self.role_var, width=28, state="readonly")
        role_combo['values'] = [role["id"] for role in self.model.get_roles()]
        role_combo.grid(row=3, column=1, sticky="ew", pady=2)

        # Active
        ttk.Label(frm, text="Active:").grid(row=4, column=0, sticky="w", pady=2)
        self.active_var = tk.BooleanVar(value=user.get("active", True) if user else True)
        ttk.Checkbutton(frm, variable=self.active_var).grid(row=4, column=1, sticky="w", pady=2)

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="OK", command=self._ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        center_window(self)

    def _ok(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        name = self.name_var.get().strip()
        role = self.role_var.get()
        active = self.active_var.get()
        
        if not username or not name or not role:
            messagebox.showerror("Error", "Username, Full Name, and Role are required")
            return
        
        if not self.user and not password:  # Password required for new users
            messagebox.showerror("Error", "Password is required for new users")
            return
        
        self.result = (username, password if password else None, name, role, active)
        self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1000x600")
        self.minsize(900, 520)
        
        # Hide the main window initially
        self.withdraw()

        self.model = Model()
        self._notebook = None

        # show login first
        self.after(50, self._show_login)

    def _show_login(self):
        def on_login(user):
            self.current_user = user
            self._build_main_ui(user)
            # Show and center the main window after successful login
            self.deiconify()
            center_window(self)
        login = LoginWindow(self, self.model, on_login)
        # Make sure the login window is centered
        login.after(100, lambda: center_window(login))

    def _build_main_ui(self, user):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # Only add tabs the user has permission to view
        if self.model.check_permission(user, "access_matrix", "view"):
            tab_matrix = MatrixTab(nb, self.model, user=user)
            nb.add(tab_matrix, text="Access Matrix")

        if self.model.check_permission(user, "form_generation", "view"):
            tab_gen = GenerateTab(nb, self.model, user=user)
            nb.add(tab_gen, text="Generate Forms")

        if self.model.check_permission(user, "staff_management", "view"):
            tab_cat_sys = CategorySystemTab(nb, self.model, user=user)
            nb.add(tab_cat_sys, text="Categories & Systems")

        if self.model.check_permission(user, "system_settings", "view"):
            tab_config = ConfigurationsTab(nb, self.model, user=user)
            nb.add(tab_config, text="Configurations")

        if self.model.check_permission(user, "user_management", "view"):
            tab_users = UserManagementTab(nb, self.model, user=user)
            nb.add(tab_users, text="User Management")

        if self.model.check_permission(user, "role_management", "view"):
            tab_access = AccessControlTab(nb, self.model, user=user)
            nb.add(tab_access, text="Access Control")

        self._notebook = nb

if __name__ == "__main__":
    # Ensure minimal files exist
    if not os.path.exists(DATA_FILE):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Missing file", f"Could not find {DATA_FILE} in the current directory.")
    else:
        app = App()
        app.mainloop()
