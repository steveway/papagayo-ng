import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.Arrays;
import java.util.Hashtable;
import java.util.List;
import java.util.StringTokenizer;

class Transliterator
{
  private String line;
  private char[] enter;
  private Hashtable scheme;
  private List<String> char_repeats = Arrays.asList("^", ":");
  private List<String> char_omits = Arrays.asList("m", "w");
  private List<String> char_specials = Arrays.asList("෿", ".", ",", "'", "’", "‘", "‛", "\"", "“", "-", "–", "_", ";", 
		  ":", "+", "(", ")", "{", "}", "'", "‒", "—", "­", "´", "‚", "﻿", "෾", "",
		  "[", "]", "?", "<", ">", "=", "*", "&", "^", "%", "$", "#", "@", "!", "~", "|", "\\", "/");
  private List<String> char_numbers = Arrays.asList("0", "1", "2", "3", "4", "5", "6", "7", "8", "9");
  private List<String> char_letters = Arrays.asList("a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n",
		  "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
		  "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z");
  
 
  Transliterator()
  {
    this.line = "";
    
    this.enter = new char[] { '\r', '\n' };
    
    this.scheme = new Hashtable(79);
  }
  
  private Hashtable encode_scheme()
    throws IOException
  {
    FileInputStream localFileInputStream = new FileInputStream("Scheme_Enc.txt");
    BufferedReader localBufferedReader = new BufferedReader(new InputStreamReader(localFileInputStream, "UTF8"));
    for (;;)
    {
      this.line = localBufferedReader.readLine();
      System.out.println("line");
      System.out.println(this.line);
      if (this.line == null) {
        break;
      }
      //System.out.println(line);
      this.scheme.put(this.line.substring(0, this.line.indexOf("\t")), new Transliterator.Node(this.line.substring(this.line.indexOf("\t") + 1, this.line.indexOf('*')), this.line.substring(this.line.indexOf('*') + 1)));
       System.out.println("1++++");
      System.out.println(this.line.substring(0, this.line.indexOf("\t")));
       System.out.println("2+++");
      System.out.println(this.line.substring(this.line.indexOf("\t") + 1, this.line.indexOf('*')));
       System.out.println("3++++");
      System.out.println(this.line.substring(this.line.indexOf('*') + 1));
    }
    localBufferedReader.close();
    return this.scheme;
  }

  public void encoder(BufferedReader paramBufferedReader, BufferedWriter paramBufferedWriter)
    throws IOException
  {
    encode_scheme();
    
    FileOutputStream localFileOutputStream = new FileOutputStream(new File("Out.txt"));
    BufferedWriter localBufferedWriter = new BufferedWriter(new OutputStreamWriter(localFileOutputStream, "UTF16"));
	
    String str1 = "";
    String str2 = "";
    String str3 = "";
    for (;;)
    {
      this.line = paramBufferedReader.readLine();
      
      int index =0;
      if (this.line == null) {
        break;
      }
      StringTokenizer localStringTokenizer = new StringTokenizer(this.line, " ");
      index = index +1;
      System.out.println("localStringTokenizer");
      System.out.println(localStringTokenizer);
	//  System.out.println("index = " + index);
      str2 = "";
      
      while (localStringTokenizer.hasMoreTokens())
      {
    	  
        str1 = localStringTokenizer.nextToken();
    localBufferedWriter.write(str1.concat("\t"));
  
		//System.out.println(str1);
		
        for (int i = 0; i < str1.length(); i++) {
        	localBufferedWriter.write("\n" + str1.charAt(i));
			localBufferedWriter.write("\t" + String.valueOf(str1.charAt(i)));
          if (!String.valueOf(str1.charAt(i)).equals("?")) {
            if (this.scheme.containsKey(String.valueOf(str1.charAt(i))))
            {
            	localBufferedWriter.write("\n"+"containskey");
              Transliterator.Node localNode = (Transliterator.Node)this.scheme.get(String.valueOf(str1.charAt(i)));
              localBufferedWriter.write("\n" + localNode.Word + " " + localNode.Cat);
              //System.out.println(localNode.Word);
              //System.out.println(localNode.Cat);
              
              if (localNode.Cat.equals("m")) {						//If the character is a modifier
            	  if(localNode.Word.equals("x")){
            		  str3 = str3;
            	  }
            	  else{
            		  str3 = str3.substring(0, str3.length() - 2);
            	  }
              }
              if(localNode.Word.equals("")){						//If the modifier is a 'hal'
            	  str3 = str3.concat(localNode.Word);
              }
              else
            	  str3 = str3.concat(localNode.Word).concat("-");
              if (localNode.Cat.equals("c")) {
            	  if(!(localNode.Word.equals("x")) || !(localNode.Word.equals("x"))){
            		  str3 = str3.concat("@-");
            	  }
              }
            }
            else													// When there is a zero-width-joiner
            {
            	localBufferedWriter.write("\n" + "elseeeeeeeeeeeeeeee");
            	//System.out.println(String.valueOf(str1.charAt(i)));
            	if(char_specials.contains(String.valueOf(str1.charAt(i)))){
            		//System.out.println("Special Character *********************");
            		str3 = str3.concat(" ");
            	}
            	
            	else if(char_numbers.contains(String.valueOf(str1.charAt(i))) || char_letters.contains(String.valueOf(str1.charAt(i)))){
            		str3 = str3.concat(String.valueOf(str1.charAt(i)));
            	}
            	else{
					if(i>3){											// If it is in the middle of the word Repeat the proceeding phone
					//	localBufferedWriter.write("\n" + str3.length());
					//	localBufferedWriter.write("\n" + str3 + "\t" + i);
						
						String last_char= str3.substring(str3.length()-2, str3.length()-1);
						if(char_repeats.contains(last_char)){			// If the proceeding phone has two chars
							str3 = str3.concat(str3.substring(str3.length()-3, str3.length()));
						}
						else if(char_omits.contains(last_char)){		// Do not repeat the proceeding phone for these phones
							str3 = str3.substring(0, str3.length());
						}
						else											// If the proceeding phone has only one char
							str3 = str3.concat(str3.substring(str3.length()-2, str3.length()));
					}
				/*	if(i<=2){											// If ZWJ is in the start of the word
						localBufferedWriter.write("\n" + str3 + "\t" + i);
						str3 = str3.concat(String.valueOf(str1.charAt(i)));
					}
					else{
						localBufferedWriter.write("\n" + str3 + "\t" + i);
						str3 = str3.concat(String.valueOf(str1.charAt(i))).concat("-");
					}*/
            	}
            }
          }
        }
        str2 = str2.concat(str3).concat(" ");
        //System.out.println(str2);
		
        str3 = "";
      }
      //paramBufferedWriter.write(str1.concat("\t"));
      System.out.println(str2);
      paramBufferedWriter.write(str2.trim());
      paramBufferedWriter.write(this.enter);
    }
    paramBufferedReader.close();
    localBufferedWriter.close();
  }


  public String encoder(String word)
    throws IOException
  {
    encode_scheme();
    
    FileOutputStream localFileOutputStream = new FileOutputStream(new File("Out.txt"));
    BufferedWriter localBufferedWriter = new BufferedWriter(new OutputStreamWriter(localFileOutputStream, "UTF16"));
	
    String str1 = word;
    String str2 = "";
    String str3 = "";
    for (;;)
    {
      
      int index =0;
     
      index = index +1;
	//  System.out.println("index = " + index);
      str2 = "";
    
    	  
      
		localBufferedWriter.write(str1.concat("\t"));
		//System.out.println(str1);
		
        for (int i = 0; i < str1.length(); i++) {
        	localBufferedWriter.write("\n" + str1.charAt(i));
			localBufferedWriter.write("\t" + String.valueOf(str1.charAt(i)));
          if (!String.valueOf(str1.charAt(i)).equals("?")) {
            if (this.scheme.containsKey(String.valueOf(str1.charAt(i))))
            {
            	localBufferedWriter.write("\n"+"containskey");
              Transliterator.Node localNode = (Transliterator.Node)this.scheme.get(String.valueOf(str1.charAt(i)));
              localBufferedWriter.write("\n" + localNode.Word + " " + localNode.Cat);
              //System.out.println(localNode.Word);
              //System.out.println(localNode.Cat);
              
              if (localNode.Cat.equals("m")) {						//If the character is a modifier
            	  if(localNode.Word.equals("x")){
            		  str3 = str3;
            	  }
            	  else{
            		  str3 = str3.substring(0, str3.length() - 2);
            	  }
              }
              if(localNode.Word.equals("")){						//If the modifier is a 'hal'
            	  str3 = str3.concat(localNode.Word);
              }
              else
            	  str3 = str3.concat(localNode.Word).concat("-");
              if (localNode.Cat.equals("c")) {
            	  if(!(localNode.Word.equals("x")) || !(localNode.Word.equals("x"))){
            		  str3 = str3.concat("@-");
            	  }
              }
            }
            else													// When there is a zero-width-joiner
            {
            	localBufferedWriter.write("\n" + "elseeeeeeeeeeeeeeee");
            	//System.out.println(String.valueOf(str1.charAt(i)));
            	if(char_specials.contains(String.valueOf(str1.charAt(i)))){
            		//System.out.println("Special Character *********************");
            		str3 = str3.concat(" ");
            	}
            	
            	else if(char_numbers.contains(String.valueOf(str1.charAt(i))) || char_letters.contains(String.valueOf(str1.charAt(i)))){
            		str3 = str3.concat(String.valueOf(str1.charAt(i)));
            	}
            	else{
					if(i>3){											// If it is in the middle of the word Repeat the proceeding phone
					//	localBufferedWriter.write("\n" + str3.length());
					//	localBufferedWriter.write("\n" + str3 + "\t" + i);
						
						String last_char= str3.substring(str3.length()-2, str3.length()-1);
						if(char_repeats.contains(last_char)){			// If the proceeding phone has two chars
							str3 = str3.concat(str3.substring(str3.length()-3, str3.length()));
						}
						else if(char_omits.contains(last_char)){		// Do not repeat the proceeding phone for these phones
							str3 = str3.substring(0, str3.length());
						}
						else											// If the proceeding phone has only one char
							str3 = str3.concat(str3.substring(str3.length()-2, str3.length()));
					}
				/*	if(i<=2){											// If ZWJ is in the start of the word
						localBufferedWriter.write("\n" + str3 + "\t" + i);
						str3 = str3.concat(String.valueOf(str1.charAt(i)));
					}
					else{
						localBufferedWriter.write("\n" + str3 + "\t" + i);
						str3 = str3.concat(String.valueOf(str1.charAt(i))).concat("-");
					}*/
            	}
            }
          }
        }
        str2 = str2.concat(str3).concat(" ");
        //System.out.println(str2);
		
        str3 = "";
      
      //paramBufferedWriter.write(str1.concat("\t"));
      //System.out.println(str2);

      //spliting phonemes into array

      String[] phonems =  str2.split("-");
      System.out.println(Arrays.toString(phonems));

      return str2;
      
    }

  } 
  
  

  private class Node
  {
    String Word;
    String Cat;
    
    Node(String paramString1, String paramString2)
    {
      this.Word = paramString1;
      this.Cat = paramString2;
    }
  }
}
