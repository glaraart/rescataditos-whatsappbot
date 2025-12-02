# Guía: Sistema de Asignación de Gastos a Animales

## 📋 Resumen

Sistema que permite registrar gastos NO veterinarios con múltiples items y asignarlos automáticamente a animales específicos o distribuirlos entre animales activos en el refugio.

**⚠️ IMPORTANTE**: Los gastos VETERINARIOS (consultas, cirugías, medicamentos) se manejan en el tipo de mensaje **VETERINARIA**, NO en GASTO.

## 🔀 Tipos de Mensaje

### `veterinaria` (nuevo)
- **Qué registra**: Visitas veterinarias + gastos veterinarios
- **Datos médicos**: diagnóstico, tratamiento, próxima_cita, veterinario
- **Datos financieros**: items de gastos (consulta, cirugía, análisis, medicamentos)
- **Inserta en**: `visitas_vet` + `gastos` (categoria_id=1) + `gasto_animal`

### `gasto`
- **Qué registra**: Gastos NO veterinarios
- **Categorías**: Alimento (2), Piedritas (3), Limpieza (4), Medicamentos generales (5), Transporte (6), Otros (7)
- **Inserta en**: `gastos` + `gasto_animal` (solo categorías 2 y 3)
- **NO incluye**: Gastos veterinarios → esos van a `veterinaria`

## 🏗️ Arquitectura

### Modelo de Datos

**GastoItem** (app/models/analysis.py):
```python
class GastoItem(BaseModel):
    monto: float
    categoria_id: int
    descripcion: str
    nombre_animal: Optional[str] = None  # Nuevo campo
```

**GastoDetails**:
```python
class GastoDetails(BaseModel):
    nombre: Optional[str] = None
    fecha: Optional[str] = None
    proveedor: Optional[str] = None
    responsable: Optional[str] = None
    forma_de_pago: Optional[str] = None
    items: List[GastoItem]  # Array de items
```

### Estructura de Base de Datos

**Tabla: gastos**
- gasto_id (PK, auto-increment)
- fecha
- categoria_id
- monto_total
- descripcion
- proveedor
- responsable
- forma_de_pago
- foto (URL de Drive)
- id_foto (Drive file ID)

**Tabla: gasto_animal** (Junction table)
- gasto_id (FK → gastos)
- animal_id (FK → animales)
- monto (porción del gasto asignada al animal)

## 🔄 Flujo de Procesamiento

### 1. Extracción por IA (OpenAI GPT-4o)

El prompt extrae:
```json
{
    "fecha": "2025-11-20 15:30:00",
    "proveedor": "Veterinaria Plus",
    "responsable": "María",
    "forma_de_pago": "efectivo",
    "items": [
        {
            "monto": 1200,
            "categoria_id": 7,
            "descripcion": "HUESO DE FEMUR MAYORAL",
            "nombre_animal": "Panchi"
        },
        {
            "monto": 6000,
            "categoria_id": 2,
            "descripcion": "Comida balanceada para gatos",
            "nombre_animal": null
        }
    ]
}
```

**Reglas de extracción de `nombre_animal`**:
- "para [nombre]" → extraer "nombre"
- "de [nombre]" → extraer "nombre"
- "[nombre]:" → extraer "nombre"
- Gasto general → null

### 2. Validación (GastoHandler.validate)

Valida:
- ✅ Array `items` existe y tiene al menos 1 item
- ✅ Cada item tiene: monto, categoria_id, descripcion
- ✅ Campos opcionales: fecha, proveedor, responsable, forma_de_pago

### 3. Confirmación

Mensaje con botones interactivos mostrando:
- Listado de items con monto y categoría
- Nombre del animal si aplica: `HUESO: $1200 (Otros) - Panchi`
- Total general

### 4. Guardado en DB (GastoHandler.save_to_db)

#### Paso A: Subir imagen a Drive
- Una imagen por ticket (compartida por todos los items)
- Carpeta: GASTOS
- Retorna: image_url + drive_file_id

#### Paso B: Insertar en tabla `gastos`
- **UN registro por cada item** del array
- Todos comparten: fecha, proveedor, responsable, forma_de_pago, foto
- Cada uno tiene su propio: monto_total, categoria_id, descripcion

#### Paso C: Asignar a animales (tabla `gasto_animal`)

Tres casos según lógica de negocio:

**CASO 1: Gasto específico (nombre_animal presente)**
```python
if item.nombre_animal:
    # Buscar animal_id por nombre
    animal_id = db_service.check_animal_name_exists(item.nombre_animal)
    
    # Insertar UN registro en gasto_animal
    {
        "gasto_id": gasto_id,
        "animal_id": animal_id,
        "monto": item.monto  # Monto completo al animal
    }
```

**CASO 2: Gasto compartido (categoria_id 2 o 3 y sin nombre_animal)**
```python
elif item.categoria_id in [2, 3]:  # Alimento o Piedritas
    # Obtener todos los animales activos en refugio
    animales_activos = db_service.get_animales_activos_en_refugio()
    
    # Calcular monto por animal (distribución equitativa)
    monto_por_animal = item.monto / len(animales_activos)
    
    # Insertar MÚLTIPLES registros en gasto_animal
    for animal in animales_activos:
        {
            "gasto_id": gasto_id,
            "animal_id": animal["id"],
            "monto": monto_por_animal
        }
```

**CASO 3: Gasto general (otros categorías sin nombre_animal)**
```python
else:
    # NO insertar en gasto_animal
    # Ejemplos: Transporte, Limpieza, Veterinario sin animal específico
    logger.info("Gasto general, no se asigna a animales")
```

## 🗄️ Métodos de PostgresService

### `get_last_inserted_id(table_name, id_column)`
Obtiene el último ID insertado usando `currval()` de PostgreSQL.

```python
gasto_id = db_service.get_last_inserted_id("gastos", "gasto_id")
```

### `get_animales_activos_en_refugio()`
Retorna animales con:
- `activo = true`
- Último evento con `estado_id = 1` (En refugio)
- Último evento con `ubicacion_id = 1` (Refugio)

```python
animales = db_service.get_animales_activos_en_refugio()
# Retorna: [{"id": 1, "nombre": "Luna", "tipo_animal": "gato"}, ...]
```

## 📊 Categorías de Gastos

| ID | Categoría    | Distribución Automática |
|----|--------------|------------------------|
| 1  | Veterinario  | No                     |
| 2  | Alimento     | **Sí** (todos activos) |
| 3  | Piedritas    | **Sí** (todos activos) |
| 4  | Limpieza     | No                     |
| 5  | Medicamentos | No                     |
| 6  | Transporte   | No                     |
| 7  | Otros        | No                     |

## 📝 Ejemplos de Uso

### Ejemplo 1: Gasto específico para un animal
**Input:**
```
"Compré un HUESO DE FEMUR MAYORAL para Panchi por $1200"
```

**Resultado en DB:**

**gastos:**
| gasto_id | fecha | categoria_id | monto_total | descripcion | proveedor |
|----------|-------|--------------|-------------|-------------|-----------|
| 101      | 2025-11-20 | 7 | 1200 | HUESO DE FEMUR MAYORAL | null |

**gasto_animal:**
| gasto_id | animal_id | monto |
|----------|-----------|-------|
| 101      | 5 (Panchi) | 1200 |

---

### Ejemplo 2: Comida compartida
**Input:**
```
"Compré comida balanceada para gatos por $6000"
```

**Animales activos en refugio:** Luna (id=1), Michi (id=2), Tom (id=3)

**Resultado en DB:**

**gastos:**
| gasto_id | fecha | categoria_id | monto_total | descripcion |
|----------|-------|--------------|-------------|-------------|
| 102      | 2025-11-20 | 2 | 6000 | Comida balanceada para gatos |

**gasto_animal:**
| gasto_id | animal_id | monto |
|----------|-----------|-------|
| 102      | 1 (Luna)  | 2000  |
| 102      | 2 (Michi) | 2000  |
| 102      | 3 (Tom)   | 2000  |

---

### Ejemplo 3: Ticket mixto
**Input:** Ticket con foto mostrando:
```
Consulta veterinaria Luna: $800
Desparasitante Luna: $350
Arena sanitaria: $1500
```

**Resultado en DB:**

**gastos:** (3 registros, una foto compartida)
| gasto_id | categoria_id | monto_total | descripcion | foto |
|----------|--------------|-------------|-------------|------|
| 103      | 1 | 800  | Consulta veterinaria | drive_url |
| 104      | 5 | 350  | Desparasitante       | drive_url |
| 105      | 3 | 1500 | Arena sanitaria      | drive_url |

**gasto_animal:**
| gasto_id | animal_id | monto |
|----------|-----------|-------|
| 103      | 1 (Luna)  | 800   |
| 104      | 1 (Luna)  | 350   |
| 105      | 1 (Luna)  | 500   |
| 105      | 2 (Michi) | 500   |
| 105      | 3 (Tom)   | 500   |

## 🚀 Testing

Para probar el sistema:

```python
# Test 1: Gasto específico
"Compré un HUESO para Panchi por $1200"

# Test 2: Gasto compartido
"Gasté $6000 en comida para gatos"

# Test 3: Ticket con múltiples items
[Foto de ticket con varios items]
```

## ⚠️ Consideraciones

1. **Animal no encontrado**: Si `nombre_animal` no existe en DB, se registra warning pero continúa procesamiento
2. **Sin animales activos**: Si no hay animales en refugio, gasto se registra en `gastos` pero no en `gasto_animal`
3. **Distribución equitativa**: Para gastos compartidos, se divide monto en partes iguales sin considerar tamaño/tipo de animal
4. **Imagen compartida**: Una sola imagen del ticket se comparte entre todos los items

## 📌 Archivos Modificados

- ✅ `app/models/analysis.py`: Agregado `nombre_animal` a GastoItem
- ✅ `app/prompts/gasto_prompt.txt`: Actualizado para extraer nombre_animal
- ✅ `app/handlers/gasto.py`: Implementada lógica de asignación en save_to_db
- ✅ `app/services/postgres.py`: Agregados métodos get_last_inserted_id y get_animales_activos_en_refugio
