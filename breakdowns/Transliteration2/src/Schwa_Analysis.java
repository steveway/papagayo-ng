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


public class Schwa_Analysis {

	private String line;
	private char[] enter;
	private  Hashtable<String, String>  scheme;
	
	private List<String> char_numbers = Arrays.asList("0", "1", "2", "3", "4", "5", "6", "7", "8", "9");
	private List<String> char_letters = Arrays.asList("A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
			  "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z");
	  
	 
	Schwa_Analysis()
	{
	    this.line = "";
	    
	    this.enter = new char[] { '\r', '\n' };
	    
	    //this.scheme = new Hashtable(62);
	    this.scheme =  new Hashtable<String, String>();
	  }
	
	public Hashtable char_type()
		    throws IOException
		  {
		
		// Get char types for all phones
		    FileInputStream localFileInputStream = new FileInputStream("Char_Type.txt");
		    BufferedReader localBufferedReader = new BufferedReader(new InputStreamReader(localFileInputStream, "UTF8"));
		    int index = 0;
		    for (;;)
		    {
		    	index = index+1;
		      this.line = localBufferedReader.readLine();
		      if (this.line == null) {
		        break;
			  }
			  
			  this.scheme.put(this.line.substring(0, this.line.indexOf("\t")), this.line.substring(this.line.indexOf("\t")+1, this.line.length()));
			  System.out.println(this.line.substring(this.line.indexOf("\t")+1, this.line.length()));
		    }
		    localBufferedReader.close();
		    return this.scheme;
		  }
	
	public String rule_one(String word) throws IOException{
		// Implements Rule #1 - Replace first syllable schwa with /a/
		
		String[] phones = word.split("-");
		String trans = "";
		if(this.scheme.containsKey(phones[0])){			// Get first phone of the word
			String value = this.scheme.get(phones[0]);	// Get char type
			if(value.equals("c")){						// If first phone is a consonant
				if(phones.length > 2){					// If word length > 2 (omit one or two letter words)
					if(phones[0].equals("k")){			//If First phone is /k/ and 
						if((phones[1].equals("@"))){		// second phone is schwa and
							if(!(phones[2].equals("r"))){		// third phone is NOT /r/, then
								phones[1] = "a";				// Replace schwa with /a/
							}
						}
					}
					else if(phones[1].equals("@")){			// If second phone is Schwa
						phones[1] = "a";				// Replace it with /a/
					}
				}
			}
		}
		
		for(String phone : phones){
			trans = trans.concat(phone).concat("-");	// construct the transliterated word
		}
		return trans;
	}
	
	
	public String rule_two(String word) throws IOException{
		// Implements Rule #2 - Occurrences with /r/ and /h/
		String[] phones = word.split("-");
		String trans = "";
		for(int i=1; i<phones.length; i++){					// Rule #2 - (a) & (b)
			String phone = phones[i];
			
			if(phone.equals("r")){							// If the phone is /r/
				if(phones.length > 2){
					String prev_phone = phones[i-1];
					String prev_type = this.scheme.get(prev_phone);
					if(prev_type.equals("c")){				// If the preceding phone is a consonant
						if(i+3 < phones.length){
							String next_phone = phones[i+1];
							if(next_phone.equals("@")){		// /r/ is followed by /@/ and,
								String nnext_phone = phones[i+2];
								String nnext_type = this.scheme.get(nnext_phone);
								if(nnext_type.equals("c")){		// /@/ is followed by any consonant (/h/ or !/h/)
									phones[i+1] = "a";
								}
							}
						}
					}
				}
			}
			
		}
				
		for(int i=1; i<phones.length; i++){					// Rule #2 - (c) & (d)
			String phone = phones[i];
			
			if(phone.equals("r")){							// If the phone is /r/
				if(phones.length > 2){
					String prev_phone = phones[i-1];
					String prev_type = this.scheme.get(prev_phone);
					if(prev_type.equals("c")){				// If the preceding phone is a consonant
						if(i+3 < phones.length){
							String next_phone = phones[i+1];
							if(next_phone.equals("a")){		// /r/ is followed by /a/ and,
								String nnext_phone = phones[i+2];
								if(!(nnext_phone.equals("h"))){		// /a/ is followed by any consonant other than /h/
									phones[i+1] = "@";
								}
							}
						}
					}
				}
			}
		}
		
		for(String phone : phones){
			trans = trans.concat(phone).concat("-");	// construct the transliterated word
		}
		
		return trans;
	}
	
	
	public String rule_three(String word) throws IOException{
		// Implements Rule #3 - If /a/, /e/, /ae/, /o/, /@/ is followed by /h/ and /h/ is preceded by /@/
		
		String[] phones = word.split("-");
		String trans = "";
		
		List<String> selected_phones = Arrays.asList("a", "e", "ae", "o", "@");
		
		for(int i=0; i<phones.length; i++){
			String phone = phones[i];
			
			if(selected_phones.contains(phone)){		// If the phone is one of the given phones
				if(i+3 <= phones.length){
					String next_phone = phones[i+1];
					if(next_phone.equals("h")){			// If that phone is followed by /h/
						String nnext_phone = phones[i+2];
						if(nnext_phone.equals("@")){	// If /h/ is preceded by /@/ ??????????????
							phones[i+2] = "a";
						}
					}
				}
				
			}
			
		}
		
		for(String phone : phones){
			trans = trans.concat(phone).concat("-");	// construct the transliterated word
		}
					
		return trans;
	}

	public String rule_four(String word) throws IOException{
		// Implements Rule #4 - If /@/ is followed by consonant cluster
		
		String[] phones = word.split("-");
		String trans = "";
		//System.out.println(Arrays.toString(phones)); 
		for(int i=0; i<phones.length; i++){
			String phone = phones[i];
			
			if(phone.equals("@")){					// If the phone is /@/
				if(i+3 <= phones.length){
					
					String next_phone = phones[i+1];
					String nnext_phone = phones[i+2];
					
					String next_type = this.scheme.get(next_phone);
					String nnext_type = this.scheme.get(nnext_phone);
					//System.out.println(word + " "+next_phone+"> "+next_type+" "+nnext_phone+"> "+nnext_type);
					//System.out.println(word);

					if(next_type.equals("c") && nnext_type.equals("c")){		// If the next two phones are consonants
						phones[i] = "a";
					}
				}
			}
		}
		
		for(String phone : phones){
			trans = trans.concat(phone).concat("-");	// construct the transliterated word
		}
		
		return trans;
	}
		

	public String rule_five(String word) throws IOException{
		// Implements Rule #5 - If /@/ is followed by words final constant
		
		String[] phones = word.split("-");
		String trans = "";
		
		List<String> selected_phones = Arrays.asList("r", "b", "t", "d");
		
		if(phones.length > 3){
			if(phones[phones.length-2].equals("@")){				// If the phone before final phone is /@/ 
				String last_phone = phones[phones.length-1];
				//System.out.println(String.valueOf(last_phone.charAt(0)));
				if(char_numbers.contains(String.valueOf(last_phone.charAt(0))) || char_letters.contains(String.valueOf(last_phone.charAt(0)))){
					
					System.out.println("Numberrrrrrrrrrrrrrrrrrr");
				}
				else{
					if(!(selected_phones.contains(last_phone))){		// If final phone is not in selected list
						String last_type = this.scheme.get(last_phone);
						if(last_type.equals("c")){						// If the final phone is a constant
							phones[phones.length-2] = "a";
						}
					}
				}
			}
		}
		
		for(String phone : phones){
			trans = trans.concat(phone).concat("-");	// construct the transliterated word
		}
		
		return trans;
	}

	public String rule_six(String word) throws IOException{
		// Implements Rule #6 - If word's final syllable is 'yi' or 'wu' and it is preceded by /@/
		
		String[] phones = word.split("-");
		String trans = "";
		
		List<String> selected_phrases = Arrays.asList("yi", "wu");
		if(phones.length >= 4){
			String phone_before_last = phones[phones.length-2];
			String phone_last = phones[phones.length-1];
			
			String phrase = phone_before_last.concat(phone_last);
			
			if(selected_phrases.contains(phrase)){					// If the last syllable of the word is 'yi' or 'wu'
				String phone = phones[phones.length-3];
				if(phone.equals("@")){								// If it is preceded by /@/
					phones[phones.length-3] = "a";
				}
			}
		}
		for(String phone : phones){
			trans = trans.concat(phone).concat("-");	// construct the transliterated word
		}
		
		return trans;
	}

	
	public String rule_seven(String word) throws IOException{
		// Implements Rule #7 - If /k/ is followed by /@/, and /@/ is followed by /r/ ot /l/ and then by /u/
		
		String[] phones = word.split("-");
		String trans = "";
		for(int i=0; i<phones.length; i++){
			String phone = phones[i];
			
			if(phones.length-i > 4){
				if(phone.equals("k")){						// If the considering phone is /k/
					String next_phone = phones[i+1];
					if(next_phone.equals("@")){				// If /k/ is preceded by /@/
						String nnext_phone = phones[i+2];
						if(nnext_phone.equals("r") || nnext_phone.equals("l")){		// If next phone is /r/ or /l/
							String nnnext_phone = phones[i+3];
							if(nnnext_phone.equals("u")){				// If /r/ or /l/ is followed by /u/
								phones[i+1] = "a";
							}
						}
					}
				}
			}
		}
		
		for(String phone : phones){
			trans = trans.concat(phone).concat("-");	// construct the transliterated word
		}
		
		return trans;
	}
	
	public String rule_eight(String word) throws IOException{
		// Implements Rule #8 - If word start's with /kal/ in several words as follows
		// /kal(a:|e:|o:)y/->/k@l(a:|e:|o:)y/
		// /kale(m|h)(u|i)/->/k@le(m|h)(u|i)/
		// /kal@h(u|i)/->/k@l@h(u|i)/
		// /kal@/->/k@l@/
		
		
		String[] phones = word.split("-");		
		String trans = "";
		
		List<String> first_set = Arrays.asList("a:", "e:", "o:");
		List<String> second_set = Arrays.asList("m", "h");
		List<String> third_set = Arrays.asList("u", "i");
		
		
		if(phones.length >= 5){
			String first_phones = phones[0].concat(phones[1]).concat(phones[2]);
			if(first_phones.equals("kal")){				// If word starts with /kal/
				String next_phone = phones[3];
				if(first_set.contains(next_phone) && phones[4].equals("y")){		// /kal(a:|e:|o:)y/->/k@l(a:|e:|o:)y/ 
					phones[1] = "@";
				}
			}
		}
		
		if(phones.length >= 6){
			String first_phones = phones[0].concat(phones[1]).concat(phones[2]).concat(phones[3]);
			if(first_phones.equals("kale")){
				String next_phone = phones[4];
				String nnext_phone = phones[5];
				if(second_set.contains(next_phone) && third_set.contains(nnext_phone)){		// /kale(m|h)(u|i)/->/k@le(m|h)(u|i)/
					phones[1] = "@";
				}
			}
			
			String next_phones = phones[0].concat(phones[1]).concat(phones[2]).concat(phones[3]).concat(phones[4]);
			if(next_phones.equals("kal@h")){
				String next_phone = phones[5];
				if(third_set.contains(next_phone)){			// /kal@h(u|i)/->/k@l@(u|i)/
					phones[1] = "@";
				}
			}
		}
		
		if(phones.length < 5 && phones.length > 3){
			String first_phones = phones[0].concat(phones[1]).concat(phones[2]).concat(phones[3]);
			if(first_phones.equals("kal@")){				// /kal@/->/k@l@/
				phones[1] = "@";
			}
		}
		
		
		for(String phone : phones){
			trans = trans.concat(phone).concat("-");	// construct the transliterated word
		}
		
		return trans;
		
	}

	public static void main(String[] args) throws IOException {
		// TODO Auto-generated method stub
		
		Schwa_Analysis sa = new Schwa_Analysis();
		Hashtable<String, String> charType = sa.char_type();
		
		try {
			FileInputStream localFileInputStream = new FileInputStream(new File("output_en.txt"));
			BufferedReader localBufferedReader = new BufferedReader(new InputStreamReader(localFileInputStream));
			
			FileOutputStream localFileOutputStream = new FileOutputStream(new File("output_EnTrans.txt"));
		    BufferedWriter localBufferedWriter = new BufferedWriter(new OutputStreamWriter(localFileOutputStream));
		      
		
			String line = localBufferedReader.readLine();
			while(line != null){
				String translit_word = sa.rule_one(line);
				translit_word = sa.rule_two(translit_word);
				translit_word = sa.rule_three(translit_word);
				translit_word = sa.rule_four(translit_word);
				translit_word = sa.rule_five(translit_word);
				translit_word = sa.rule_six(translit_word);
				translit_word = sa.rule_seven(translit_word);
				translit_word = sa.rule_eight(translit_word);
				//System.out.println(translit_word);
				
				localBufferedWriter.write(translit_word + "\n");
				
				line = localBufferedReader.readLine();
			}
			
			localBufferedWriter.close();
			localBufferedReader.close();
			
			
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		} 
		
		
	}

}
