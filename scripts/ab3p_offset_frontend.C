/*
 * Versioned offset-emitting frontend for the unchanged Ab3P library.
 *
 * The upstream identify_abbr frontend processes one getline() line at a time.
 * Keep that contract exactly: this program calls Ab3P::get_abbrs once for
 * every input line and emits the same detected pair strings, precision and
 * strategy, together with the native byte offsets exposed by AbbrOut.
 */

#include "Ab3P.h"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using namespace iret;
using namespace std;

namespace {

const char *const schema_version = "ab3p-offsets-v1";

string json_escape(const string &value) {
  string result;
  result.reserve(value.size() + 2);
  for (unsigned char character : value) {
    switch (character) {
    case '"':
      result += "\\\"";
      break;
    case '\\':
      result += "\\\\";
      break;
    case '\b':
      result += "\\b";
      break;
    case '\f':
      result += "\\f";
      break;
    case '\n':
      result += "\\n";
      break;
    case '\r':
      result += "\\r";
      break;
    case '\t':
      result += "\\t";
      break;
    default:
      if (character < 0x20) {
        result += "\\u00";
        const char *digits = "0123456789abcdef";
        result += digits[(character >> 4) & 0x0f];
        result += digits[character & 0x0f];
      } else {
        result += static_cast<char>(character);
      }
    }
  }
  return result;
}

void emit(const string &line, unsigned long long line_index,
          unsigned long long line_start_byte, const AbbrOut &abbreviation) {
  cout << "{\"schema_version\":\"" << schema_version
       << "\",\"line_index\":" << line_index
       << ",\"line_start_byte\":" << line_start_byte
       << ",\"line_byte_length\":" << line.size()
       << ",\"short_form\":\"" << json_escape(abbreviation.sf)
       << "\",\"long_form\":\"" << json_escape(abbreviation.lf)
       << "\",\"precision\":" << setprecision(17) << abbreviation.prec
       << ",\"strategy\":\"" << json_escape(abbreviation.strat)
       << "\",\"sf_offset\":" << abbreviation.sf_offset
       << ",\"lf_offset\":" << abbreviation.lf_offset << "}\n";
}

} // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    cerr << "Usage: " << argv[0] << " filename\n";
    return 1;
  }

  ifstream input(argv[1], ios::in | ios::binary);
  if (!input) {
    cerr << "Cannot open " << argv[1] << '\n';
    return 1;
  }

  Ab3P ab3p;
  vector<AbbrOut> abbreviations;
  string line;
  unsigned long long line_index = 0;
  unsigned long long line_start_byte = 0;
  while (getline(input, line)) {
    ab3p.get_abbrs(line, abbreviations);
    for (const AbbrOut &abbreviation : abbreviations) {
      emit(line, line_index, line_start_byte, abbreviation);
    }
    line_start_byte += line.size() + 1;
    ++line_index;
  }

  return 0;
}
