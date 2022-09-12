#!/usr/bin/env python3
import sys, os
from requests import patch
import argparse
import shutil
import traceback


try:
  rec_path = os.path.dirname(os.path.realpath(__file__))
  rec_path += "\\recipe_scripts\\"
  sys.path.append(rec_path)
  import recipe_constructor as rc
except:
  print("[update_patch_table] Error: Can't import Recipe scripts.")
  print(traceback.format_exc())
  exit(1)


# Create a knob list object from emb_recipe
def get_knobs(recipe):
  knob_list = []      # List of knobs with end qualifier -> "),"
  # Populate knobs list 
  for ifwi in recipe.release_set:
    for knob in ifwi.knobs:
      if knob not in knob_list:
        knob_list.append(knob + "),")
  return knob_list

# Check if line has knob
def line_offends(x, offending):
  ret_str = ""
  for word in x:
    if word in offending:
      word = word.strip("),")
      print("[update_patch_table] Info: Removing knob from patch table - " + word)
      ret_str += " >>>>> ***** Removed *****\n"
      return ret_str
  return ret_str

def dump_pt(line):
  ret_str = ""
  if "CONFIG_PATCH" in line and "[]" in line:
    ret_str += "\n-------------------------------------------------------------------------------------------\n"
    ret_str += "Table: " + line.split()[1].strip("[]") + "\n"
    print("[update_patch_table] Info: Parsing table - " + line.split()[1].strip("[]"))
  elif "OFFSET_OF" in line:
    #print(line.split()[4].strip("),"))

    x = line.replace(" ", "")
    x = x.replace("\t", "")
    x = x.replace("\n", "") 
    x = x.split(",")
    ret_str += "  Knob: " + x[3][:-1] + " -> " + x[4].replace("}", "")
    print(ret_str)
  return ret_str

def update_patch_table(recipe, base_workspace_dir):
  try:
    pt_path = os.path.join(base_workspace_dir, recipe.patch_table_path)
    if not pt_path:
      raise
  except:
    print("[update_patch_table] Info: No patch table found. Exiting.")
    return 0
  orig = os.path.join(base_workspace_dir, os.path.dirname(pt_path), os.path.basename(pt_path) + "_orig" + os.path.splitext(pt_path)[1])
  shutil.copy(pt_path, orig)
  # Generate knobs list from recipe
  knob_list = get_knobs(recipe)
  # Open up patch table and iterate through line by line
  with open(orig) as fin, open(pt_path, 'w') as fout, open('pt_report.txt', 'w') as pt:
    title_str = "\n***** Patch Table Report"
    if recipe.edkrepo_pin:
      title_str += " for BIOS: " + recipe.edkrepo_pin
    elif recipe.bios_version:
      title_str += " for BIOS: " +  recipe.bios_version
    title_str += " *****\n"
    pt.write(title_str)
    for line in fin:
      rept_str = dump_pt(line)
      x = line.split()
      offended = line_offends(x, knob_list)
      if offended:
        rept_str += offended
        # End of array case
        if x.pop() == "}":
          fout.write("  {0x0}\n")
        else:
          fout.write("  {0x0},\n")
      else:
        if rept_str:
          rept_str += "\n"
        fout.write(line)
      pt.write(rept_str)

def get_args():
  parser = argparse.ArgumentParser(description="If knobs exist in patch table, remove them before compiling")
  parser.add_argument("-r", "--recipe",             help="A recipe .yml", required=True)
  parser.add_argument("-b", "--base_workspace_dir", help="Path to the workspace where the source code is", required=True)
  return parser.parse_args()

if __name__ == '__main__':
  args = get_args()
  recipe = rc.get_recipe(args.recipe)
  update_patch_table(recipe, args.base_workspace_dir)