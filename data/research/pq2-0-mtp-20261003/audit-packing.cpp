// Research reproduction: decode both pinned formats using the scalar reference layout.
// Called by audit-packing.py; compiler output stays in its temporary directory.
#include <array>
#include <cstdint>
#include <fstream>
#include <future>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
struct Tensor {std::string name; uint64_t pt,pq,blocks;};
struct Counts {uint64_t weights=0,mismatch=0,scale_mismatch=0,plus2=0,scale_code3=0;};
int main(int argc,char **argv) {
 if(argc!=4)return 2;
 std::ifstream manifest(argv[3]);std::vector<Tensor> tensors;Tensor t;
 while(manifest>>t.name>>t.pt>>t.pq>>t.blocks)tensors.push_back(t);
 if(tensors.size()!=402)throw std::runtime_error("expected 402 tensors");
 std::array<std::array<unsigned char,5>,256> digits{};
 for(unsigned b=0;b<256;b++){unsigned q=b;for(unsigned k=0;k<5;k++){q*=3;digits[b][k]=q>>8;q&=255;}}
 std::vector<std::future<Counts>> workers;
 for(size_t worker=0;worker<4;worker++)workers.emplace_back(std::async(std::launch::async,[&,worker]{
  std::ifstream pt(argv[1],std::ios::binary),pq(argv[2],std::ios::binary);Counts counts;
  std::vector<unsigned char> pa(34*8192),ta(28*8192);
  for(size_t index=worker;index<tensors.size();index+=4){const auto & tensor=tensors[index];
   pt.seekg(tensor.pt);pq.seekg(tensor.pq);
   for(uint64_t start=0;start<tensor.blocks;start+=8192){size_t n=std::min(uint64_t(8192),tensor.blocks-start);
    pt.read(reinterpret_cast<char*>(ta.data()),n*28);pq.read(reinterpret_cast<char*>(pa.data()),n*34);
    if(!pt||!pq)throw std::runtime_error("short read");
    for(size_t block=0;block<n;block++){auto * p=&pa[block*34];auto * q=&ta[block*28];
     counts.scale_mismatch+=(p[0]!=q[26]||p[1]!=q[27]);
     for(int s=0;s<2;s++)for(int bit=0;bit<8;bit+=2)counts.scale_code3+=((p[s]>>bit)&3)==3;
     unsigned pos=0;
     auto check=[&](unsigned digit){unsigned code=(p[2+pos/4]>>((pos%4)*2))&3;counts.mismatch+=digit!=code;counts.plus2+=code==3;pos++;};
     for(unsigned k=0;k<5;k++)for(unsigned byte=0;byte<16;byte++)check(digits[q[byte]][k]);
     for(unsigned k=0;k<5;k++)for(unsigned byte=16;byte<24;byte++)check(digits[q[byte]][k]);
     for(unsigned k=0;k<4;k++)for(unsigned byte=24;byte<26;byte++)check(digits[q[byte]][k]);
     counts.weights+=128;
    }
   }
  }return counts;
 }));
 Counts sum;for(auto & w:workers){auto c=w.get();sum.weights+=c.weights;sum.mismatch+=c.mismatch;sum.scale_mismatch+=c.scale_mismatch;sum.plus2+=c.plus2;sum.scale_code3+=c.scale_code3;}
 std::cout<<"{\"weights\":"<<sum.weights<<",\"different_codes\":"<<sum.mismatch<<",\"different_scale_blocks\":"<<sum.scale_mismatch<<",\"pq2_plus2\":"<<sum.plus2<<",\"scale_byte_code3_if_misread\":"<<sum.scale_code3<<"}\n";
 return sum.mismatch||sum.scale_mismatch?1:0;
}
